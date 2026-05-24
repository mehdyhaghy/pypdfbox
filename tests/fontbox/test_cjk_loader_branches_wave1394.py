"""Wave 1394 — defensive branches in ``pypdfbox.fontbox.cjk_loader``.

Covers lines 179-185 (``target.parent.mkdir`` OSError path) and 242-243
(the ``_extract_regular`` ``finally`` branch where the partial file is
left dangling and gets unlinked).
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from pypdfbox.fontbox import cjk_loader


@contextmanager
def _opt_in(monkeypatch: pytest.MonkeyPatch, cache_dir: Path) -> None:
    monkeypatch.setenv("PYPDFBOX_CJK_AUTODOWNLOAD", "1")
    monkeypatch.setenv("PYPDFBOX_CJK_CACHE_DIR", str(cache_dir))
    yield


def _make_zip(font_filename: str, body: bytes = b"FAKE-OTF") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(font_filename, body)
        zf.writestr("LICENSE", b"OFL-1.1")
    return buf.getvalue()


def _fake_opener_for(payload: bytes):
    class _Resp:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            return self._data

    def _opener(_req, timeout: int = 0):  # noqa: ARG001
        return _Resp(payload)

    return _opener


def test_mkdir_failure_returns_none_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """``target.parent.mkdir`` raising ``OSError`` is caught and the
    loader returns ``None`` (lines 179-185)."""
    original_mkdir = Path.mkdir

    def _boom_mkdir(self: Path, *args, **kwargs):
        # Only the cache-dir create call should explode; allow other
        # mkdir invocations (none expected, but kept defensive).
        raise PermissionError("simulated permission denied")

    monkeypatch.setattr(Path, "mkdir", _boom_mkdir)

    with _opt_in(monkeypatch, tmp_path), caplog.at_level("WARNING"):
        result = cjk_loader.ensure_language("Japan1", opener=lambda *_a, **_kw: None)

    # restore (in case the rest of the test session relies on it)
    monkeypatch.setattr(Path, "mkdir", original_mkdir)
    assert result is None
    assert any("could not create cache dir" in rec.message for rec in caplog.records)


def test_extract_regular_finally_unlinks_partial_file(tmp_path: Path) -> None:
    """``_extract_regular`` uses ``tmp.replace(target)`` to swap the
    partial file into place. If ``replace`` succeeds, ``tmp.exists()``
    in the finally block returns ``False``; if ``replace`` raises, the
    finally block must unlink the stranded partial (lines 241-243).

    Drive the failure-case by passing a target whose parent we delete
    after writing the partial — `tmp.replace(target)` then raises
    FileNotFoundError, the finally branch unlinks the partial."""
    payload = _make_zip("NotoSansCJK-Regular.ttc", body=b"hello-otf")

    target_dir = tmp_path / "out"
    target_dir.mkdir()
    target = target_dir / "NotoSansCJK-Regular.ttc"

    # Trick: monkey-patch tmp.replace to fail after the write so the
    # finally branch is forced.  This avoids relying on filesystem-
    # specific behaviour for the "missing parent" approach.
    from pathlib import Path as _Path

    real_replace = _Path.replace

    def _boom_replace(self, dst):  # type: ignore[no-untyped-def]
        if str(self).endswith(".partial"):
            raise PermissionError("simulated replace failure")
        return real_replace(self, dst)

    try:
        _Path.replace = _boom_replace  # type: ignore[method-assign]
        with pytest.raises(PermissionError):
            cjk_loader._extract_regular(  # noqa: SLF001
                payload, "NotoSansCJK-Regular.ttc", target
            )
        # Partial file must have been cleaned up by the finally branch.
        partial = target.with_suffix(target.suffix + ".partial")
        assert not partial.exists(), "finally branch should unlink the partial"
    finally:
        _Path.replace = real_replace  # type: ignore[method-assign]


def test_extract_regular_success_leaves_target_only(tmp_path: Path) -> None:
    """Companion sanity test: when ``replace`` succeeds (normal flow),
    the target appears and no .partial straggler is left."""
    payload = _make_zip("NotoSansCJK-Regular.ttc", body=b"final-otf")
    target = tmp_path / "NotoSansCJK-Regular.ttc"
    cjk_loader._extract_regular(  # noqa: SLF001
        payload, "NotoSansCJK-Regular.ttc", target
    )
    assert target.is_file()
    assert not target.with_suffix(target.suffix + ".partial").exists()
    assert target.read_bytes() == b"final-otf"


def test_ensure_language_through_real_extract_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: ensure_language with a valid zip pins SHA + completes
    extraction successfully — exercises the happy path through the
    finally branch (no stranded .partial)."""
    asset = cjk_loader._MANIFEST["JP"]
    payload = _make_zip(asset.font_filename, body=b"NOTO-JP-FAKE")
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setitem(
        cjk_loader._MANIFEST,
        "JP",
        cjk_loader._Asset(
            asset_name=asset.asset_name,
            sha256=digest,
            font_filename=asset.font_filename,
        ),
    )
    with _opt_in(monkeypatch, tmp_path):
        path = cjk_loader.ensure_language("Japan1", opener=_fake_opener_for(payload))
    assert path is not None
    assert path.is_file()
    assert not path.with_suffix(path.suffix + ".partial").exists()

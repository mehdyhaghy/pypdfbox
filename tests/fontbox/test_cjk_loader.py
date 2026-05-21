"""Tests for the opt-in Noto Sans CJK auto-downloader.

The loader is original work (no upstream counterpart). These tests
exercise the contract from the perspective of callers in
:mod:`pypdfbox.pdmodel.font.font_mapper_impl`:

* Default behaviour is inert (no env var → returns ``None`` → callers
  fall through to ``.notdef`` rendering, identical to upstream PDFBox).
* When opted-in via :envvar:`PYPDFBOX_CJK_AUTODOWNLOAD`, the loader
  resolves Adobe CIDSystemInfo orderings to Noto language codes,
  downloads via an injected opener, verifies SHA-256, and extracts
  only the Regular weight into the per-user cache.
* Failure modes (bad SHA, network error, missing entry in zip) log a
  warning and return ``None`` rather than raising.

Tests use a fake in-memory zip + a stub ``opener`` so they never touch
the real network or filesystem outside ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError

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

        def __exit__(self, *exc) -> None:
            return None

        def read(self) -> bytes:
            return self._data

    def _opener(_req, timeout: int = 0):  # noqa: ARG001
        return _Resp(payload)

    return _opener


# ---------- inert defaults ----------


def test_default_is_inert_no_env_no_network(tmp_path, monkeypatch):
    monkeypatch.delenv("PYPDFBOX_CJK_AUTODOWNLOAD", raising=False)
    monkeypatch.setenv("PYPDFBOX_CJK_CACHE_DIR", str(tmp_path))

    def _exploding_opener(*_a, **_kw):  # pragma: no cover - must not be called
        raise AssertionError("opener invoked when auto-download disabled")

    assert cjk_loader.is_autodownload_enabled() is False
    assert cjk_loader.ensure_language("Japan1", opener=_exploding_opener) is None


def test_unknown_ordering_returns_none(tmp_path, monkeypatch):
    with _opt_in(monkeypatch, tmp_path):
        assert cjk_loader.ensure_language("Identity") is None
        assert cjk_loader.ensure_language("Adobe-KR") is None


# ---------- ordering -> language code mapping ----------


@pytest.mark.parametrize(
    ("ordering", "expected"),
    [
        ("Japan1", "JP"),
        ("Korea1", "KR"),
        ("GB1", "SC"),
        ("CNS1", "TC"),
        ("Identity", None),
    ],
)
def test_language_for_ordering(ordering, expected):
    assert cjk_loader.language_for_ordering(ordering) == expected


# ---------- cache_dir resolution ----------


def test_cache_dir_honours_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PYPDFBOX_CJK_CACHE_DIR", str(tmp_path / "custom"))
    assert cjk_loader.cache_dir() == tmp_path / "custom"


def test_cache_dir_xdg_cache_home(tmp_path, monkeypatch):
    monkeypatch.delenv("PYPDFBOX_CJK_CACHE_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    # Only meaningful on non-Windows; on Windows the LOCALAPPDATA branch wins.
    import sys

    if sys.platform == "win32":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert cjk_loader.cache_dir() == tmp_path / "pypdfbox" / "fonts" / "noto-cjk"
    else:
        assert cjk_loader.cache_dir() == tmp_path / "pypdfbox" / "fonts" / "noto-cjk"


# ---------- happy path ----------


def test_happy_path_downloads_verifies_and_extracts(tmp_path, monkeypatch):
    asset = cjk_loader._MANIFEST["JP"]
    body = b"NOT-A-REAL-OTF-BUT-PINNED-FOR-SHA"
    payload = _make_zip(asset.font_filename, body)
    # Pin the manifest SHA-256 to the *actual* digest of our fake payload
    # so the verify step passes deterministically.
    monkeypatch.setitem(
        cjk_loader._MANIFEST,
        "JP",
        cjk_loader._Asset(
            asset_name=asset.asset_name,
            sha256=hashlib.sha256(payload).hexdigest(),
            font_filename=asset.font_filename,
        ),
    )

    with _opt_in(monkeypatch, tmp_path):
        path = cjk_loader.ensure_language(
            "Japan1", opener=_fake_opener_for(payload)
        )

    assert path is not None
    assert path == tmp_path / asset.font_filename
    assert path.read_bytes() == body


def test_cached_file_returned_without_network(tmp_path, monkeypatch):
    asset = cjk_loader._MANIFEST["SC"]
    target = tmp_path / asset.font_filename
    target.write_bytes(b"prefetched")

    def _no_network(*_a, **_kw):  # pragma: no cover - must not be called
        raise AssertionError("opener invoked when font already cached")

    with _opt_in(monkeypatch, tmp_path):
        path = cjk_loader.ensure_language("GB1", opener=_no_network)

    assert path == target


# ---------- failure modes ----------


def test_sha_mismatch_refuses_to_extract(tmp_path, monkeypatch, caplog):
    asset = cjk_loader._MANIFEST["KR"]
    payload = _make_zip(asset.font_filename, b"corrupt")
    # Leave the pinned SHA in place so the digest will not match.

    with _opt_in(monkeypatch, tmp_path), caplog.at_level("WARNING"):
        result = cjk_loader.ensure_language(
            "Korea1", opener=_fake_opener_for(payload)
        )

    assert result is None
    assert not (tmp_path / asset.font_filename).exists()
    assert any("SHA-256 mismatch" in rec.message for rec in caplog.records)


def test_network_error_returns_none(tmp_path, monkeypatch, caplog):
    def _broken(*_a, **_kw):
        raise URLError("simulated outage")

    with _opt_in(monkeypatch, tmp_path), caplog.at_level("WARNING"):
        result = cjk_loader.ensure_language("Japan1", opener=_broken)

    assert result is None
    assert any("download failed" in rec.message for rec in caplog.records)


def test_zip_missing_regular_weight_returns_none(tmp_path, monkeypatch, caplog):
    asset = cjk_loader._MANIFEST["TC"]
    # Zip the LICENSE only — Regular weight absent.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("LICENSE", b"OFL-1.1")
    payload = buf.getvalue()
    monkeypatch.setitem(
        cjk_loader._MANIFEST,
        "TC",
        cjk_loader._Asset(
            asset_name=asset.asset_name,
            sha256=hashlib.sha256(payload).hexdigest(),
            font_filename=asset.font_filename,
        ),
    )

    with _opt_in(monkeypatch, tmp_path), caplog.at_level("WARNING"):
        result = cjk_loader.ensure_language(
            "CNS1", opener=_fake_opener_for(payload)
        )

    assert result is None
    assert any("extraction failed" in rec.message for rec in caplog.records)


# ---------- env-flag truthiness ----------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "On"])
def test_truthy_env_values(monkeypatch, value):
    monkeypatch.setenv("PYPDFBOX_CJK_AUTODOWNLOAD", value)
    assert cjk_loader.is_autodownload_enabled() is True


@pytest.mark.parametrize("value", ["", "0", "no", "false", "off", "maybe"])
def test_falsey_env_values(monkeypatch, value):
    monkeypatch.setenv("PYPDFBOX_CJK_AUTODOWNLOAD", value)
    assert cjk_loader.is_autodownload_enabled() is False

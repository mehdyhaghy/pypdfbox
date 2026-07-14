"""Coverage-boost tests for ``WriteDecodedDoc`` (wave 1323).

Targets the residual missing branches in
``pypdfbox.tools.write_decoded_doc``:

* ``do_it``'s xref-table walk (lines 39-45) — current wave-1315 tests
  use ``rot0.pdf`` whose ``COSDocument.get_xref_table()`` is empty after
  parsing, so the for-loop never iterates. Here we build a synthetic
  document with seeded xref entries and confirm the streams in the
  pool get their ``/Filter`` cleared.
* The ``AttributeError`` fallback at lines 40-41 — exercised by injecting
  a CosDocument lacking ``get_xref_table``.
* ``process_object``'s ``OSError`` arm (lines 65-67) — fed a stream with
  corrupted ``/FlateDecode`` payload so ``to_byte_array`` raises.
* The ``__name__ == "__main__"`` block (line 113) via ``runpy``.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import write_decoded_doc
from pypdfbox.tools.write_decoded_doc import WriteDecodedDoc


# ---------------------------------------------------------------------------
# Loader shim — yields a pre-built PDDocument as a context manager.
# ---------------------------------------------------------------------------
class _FixedDocLoader:
    """Loader stand-in that returns a pre-built ``PDDocument`` regardless
    of input path. Used to exercise ``do_it`` against a synthetic
    document whose xref table we control."""

    document: PDDocument | None = None

    @classmethod
    @contextlib.contextmanager
    def load_pdf(cls, source: Any, password: Any = None) -> Iterator[PDDocument]:
        assert cls.document is not None
        try:
            yield cls.document
        finally:
            pass  # caller owns close lifecycle


@pytest.fixture
def patched_loader(monkeypatch: pytest.MonkeyPatch) -> type[_FixedDocLoader]:
    """Swap the module-level ``Loader`` for the fixed-doc shim."""
    monkeypatch.setattr(write_decoded_doc, "Loader", _FixedDocLoader)
    return _FixedDocLoader


# ---------------------------------------------------------------------------
# do_it — xref-table walk with a synthetic CosDocument
# ---------------------------------------------------------------------------


def _make_pd_doc_with_xref_stream(
    payload: bytes = b"hello world",
    filter_name: COSName | None = None,
) -> tuple[PDDocument, COSStream]:
    """Build a synthetic PDDocument whose xref table carries one entry
    pointing at a FlateDecode-compressed stream sitting in the object
    pool."""
    flt = filter_name if filter_name is not None else COSName.FLATE_DECODE
    cos = COSDocument()
    key = COSObjectKey(1, 0)
    cos.add_xref_table({key: 100})
    obj = cos.get_object_from_pool(key)
    stream = COSStream()
    stream.set_item(COSName.FILTER, flt)
    with stream.create_output_stream(flt) as out:
        out.write(payload)
    obj.set_object(stream)
    return PDDocument(cos), stream


def test_do_it_walks_xref_and_clears_filter(
    patched_loader: type[_FixedDocLoader], tmp_path: Path
) -> None:
    """End-to-end ``do_it`` over a synthetic doc with one FlateDecode
    stream — confirms the xref-walk loop (lines 39-45) runs, the stream's
    ``/Filter`` is removed, and the decoded payload survives the rewrite."""
    pd, stream = _make_pd_doc_with_xref_stream(b"the quick brown fox")
    _FixedDocLoader.document = pd
    out = tmp_path / "decoded.pdf"
    try:
        runner = WriteDecodedDoc()
        runner.do_it("in.pdf", out, password=None, skip_images=False)
    finally:
        pd.close()
    assert stream.get_item(COSName.FILTER) is None
    # Decoded body round-trips through the rewrite branch verbatim.
    assert stream.get_raw_data() == b"the quick brown fox"
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_do_it_swallows_attribute_error_when_xref_table_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If the wrapped ``COSDocument`` doesn't expose
    ``get_xref_table()``, ``do_it`` falls back to ``xref_keys = []`` and
    proceeds to save without iterating — covers lines 40-41."""

    class _NoXrefCos:
        scratch_file = None

        def get_object_from_pool(self, key: Any) -> Any:  # pragma: no cover
            return None

        # No ``get_xref_table`` — triggers the AttributeError fallback.
        def set_is_xref_stream(self, value: bool) -> None:
            self._was_set = value

    class _FakePD:
        _cos = _NoXrefCos()
        saved_to: Path | None = None

        def set_all_security_to_be_removed(self, value: bool) -> None:
            self._security = value

        def get_document(self) -> _NoXrefCos:
            return self._cos

        def get_document_catalog(self) -> object:
            return object()

        def save(self, path: Any, compress_parameters: Any = None) -> None:
            self.saved_to = Path(path)

        def __enter__(self) -> _FakePD:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    fake = _FakePD()

    @contextlib.contextmanager
    def fake_loader(source: Any, password: Any = None) -> Iterator[_FakePD]:
        yield fake

    class _ShimLoader:
        load_pdf = staticmethod(fake_loader)

    monkeypatch.setattr(write_decoded_doc, "Loader", _ShimLoader)
    out = tmp_path / "out.pdf"
    WriteDecodedDoc().do_it("in.pdf", out, password=None, skip_images=False)
    assert fake.saved_to == out


# ---------------------------------------------------------------------------
# process_object — OSError arm + COSObject unwrap
# ---------------------------------------------------------------------------


class _OSErrorStream(COSStream):
    """A ``COSStream`` whose decode raises, driving the OSError-skip arm.

    Wave 1505 made FlateDecode lenient (partial output instead of raising,
    matching upstream PDFBOX-1232), so a corrupt deflate payload no longer
    produces an ``OSError`` — the skip branch is now driven directly, the
    way upstream's catch (IOException from any cause) is contract-tested.
    """

    def has_data(self) -> bool:
        # ``PDStream.to_byte_array`` short-circuits to ``b""`` when the
        # stream has no body; report data so the raising read is reached.
        return True

    def to_byte_array(self) -> bytes:
        raise OSError("synthetic decode failure")

    def create_input_stream(self, *args: object, **kwargs: object):
        # ``process_object`` reads via ``PDStream(stream).to_byte_array()``,
        # which drains this input stream — raise from here too so the
        # OSError surfaces regardless of the read path.
        raise OSError("synthetic decode failure")


def test_process_object_oserror_is_logged_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A stream whose decode raises ``OSError`` during ``to_byte_array``;
    the helper logs to stderr with the object's key — covers lines 65-67."""
    stream = _OSErrorStream()
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)

    class _ObjWithKey:
        def __init__(self, inner: COSStream) -> None:
            self._inner = inner

        def get_object(self) -> COSStream:
            return self._inner

        def get_key(self) -> str:
            return "42 0 R"

    WriteDecodedDoc().process_object(_ObjWithKey(stream), skip_images=False)
    err = capsys.readouterr().err
    assert "skip 42 0 R obj:" in err


def test_process_object_oserror_without_get_key_uses_placeholder(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the wrapped object has no ``get_key`` method, the fallback
    lambda returns ``"?"`` — covers the ``lambda: "?"`` arm of
    ``getattr(cos_object, "get_key", ...)``."""

    class _BareWrapper:
        """No ``get_object`` (so the raw stream is checked directly) and
        no ``get_key`` — forces the lambda fallback in process_object."""

        # Need this so isinstance(base, COSStream) is True after
        # process_object's unwrap step.
        pass

    inner = _OSErrorStream()
    inner.set_item(COSName.FILTER, COSName.FLATE_DECODE)

    class _CosObjShim:
        def get_object(self) -> COSStream:
            return inner
        # Deliberately no get_key — exercises the lambda fallback.

    WriteDecodedDoc().process_object(_CosObjShim(), skip_images=False)
    err = capsys.readouterr().err
    assert "skip ? obj:" in err


def test_process_object_unwraps_cos_object_via_get_object() -> None:
    """When the input has a ``get_object`` attribute, ``process_object``
    unwraps it before checking ``isinstance(.., COSStream)`` — covers
    the ``hasattr(.., "get_object")`` branch on line 53."""
    stream = COSStream()
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)
    with stream.create_output_stream(COSName.FLATE_DECODE) as out:
        out.write(b"payload")

    class _Wrapper:
        def get_object(self) -> COSStream:
            return stream

    WriteDecodedDoc().process_object(_Wrapper(), skip_images=False)
    assert stream.get_item(COSName.FILTER) is None
    assert stream.get_raw_data() == b"payload"


# ---------------------------------------------------------------------------
# __main__ block (line 113) — run the module entry-point via runpy
# ---------------------------------------------------------------------------


def test_main_block_runs_under_module_invocation(tmp_path: Path) -> None:
    """Executing the module with ``__name__ == "__main__"`` exits with
    code 4 when the input file is missing — confirms the ``if __name__``
    guard at line 113 dispatches to ``main(sys.argv[1:])``."""
    # Use subprocess so we don't pollute the test runner's argv handling.
    missing = tmp_path / "missing.pdf"
    out = tmp_path / "out.pdf"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pypdfbox.tools.write_decoded_doc",
            str(missing),
            str(out),
        ],
        check=False,
        capture_output=True,
    )
    assert proc.returncode == 4
    assert b"Error writing decoded PDF" in proc.stderr


def test_main_runner_returns_zero_on_synthetic_doc(
    patched_loader: type[_FixedDocLoader], tmp_path: Path
) -> None:
    """End-to-end ``main([..])`` against our synthetic doc returns 0 and
    writes the decoded PDF."""
    pd, _stream = _make_pd_doc_with_xref_stream(b"abc")
    _FixedDocLoader.document = pd
    out = tmp_path / "main.pdf"
    try:
        rc = WriteDecodedDoc.main(["in.pdf", str(out)])
    finally:
        pd.close()
    assert rc == 0
    assert out.exists()

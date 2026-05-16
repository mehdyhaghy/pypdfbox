"""Coverage boost for ``SignatureOptions`` (wave 1318).

Exercises the dispatch branches of ``set_visual_signature`` and
``init_from_random_access_read``, the close-time cleanup of both the
visual-signature ``COSDocument`` and the underlying file source, and the
preferred-signature-size guards.

The ``PDFParser`` is stubbed because driving a real parse from in-memory
bytes is out of scope for a unit test of this options bag.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.signature_options import (
    DEFAULT_SIGNATURE_SIZE,
    SignatureOptions,
)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


class _FakeParser:
    """Stub mirroring ``PDFParser(source).parse().get_document()``."""

    last_source: object | None = None

    def __init__(self, source: object) -> None:
        type(self).last_source = source

    def parse(self) -> MagicMock:
        wrapper = MagicMock()
        cos_doc = MagicMock()
        wrapper.get_document.return_value = cos_doc
        return wrapper


def _patch_parser():
    """Patch the ``PDFParser`` symbol that ``_init_from_input`` imports."""
    return patch("pypdfbox.pdfparser.pdf_parser.PDFParser", _FakeParser)


# ----------------------------------------------------------------------
# defaults / setters
# ----------------------------------------------------------------------


def test_default_signature_size_constant_matches_class_attr() -> None:
    assert SignatureOptions.DEFAULT_SIGNATURE_SIZE == DEFAULT_SIGNATURE_SIZE
    assert DEFAULT_SIGNATURE_SIZE == 0x2500


def test_get_page_and_visual_signature_default_to_zero_and_none() -> None:
    opts = SignatureOptions()
    try:
        assert opts.get_page() == 0
        assert opts.get_visual_signature() is None
        assert opts.get_preferred_signature_size() == 0
    finally:
        opts.close()


def test_set_page_round_trips_zero_based_index() -> None:
    opts = SignatureOptions()
    try:
        opts.set_page(7)
        assert opts.get_page() == 7
    finally:
        opts.close()


def test_set_preferred_signature_size_accepts_positive() -> None:
    opts = SignatureOptions()
    try:
        opts.set_preferred_signature_size(1024)
        assert opts.get_preferred_signature_size() == 1024
    finally:
        opts.close()


def test_set_preferred_signature_size_ignores_non_positive() -> None:
    opts = SignatureOptions()
    try:
        opts.set_preferred_signature_size(0)
        assert opts.get_preferred_signature_size() == 0
        opts.set_preferred_signature_size(-5)
        assert opts.get_preferred_signature_size() == 0
        # A subsequent positive still wins.
        opts.set_preferred_signature_size(42)
        assert opts.get_preferred_signature_size() == 42
        # Then a non-positive must not clobber the live value.
        opts.set_preferred_signature_size(-1)
        assert opts.get_preferred_signature_size() == 42
    finally:
        opts.close()


# ----------------------------------------------------------------------
# set_visual_signature dispatch
# ----------------------------------------------------------------------


def test_set_visual_signature_from_path(tmp_path) -> None:
    pdf_path = tmp_path / "vis.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    with _patch_parser():
        opts = SignatureOptions()
        try:
            opts.set_visual_signature(pdf_path)
            assert opts.get_visual_signature() is not None
        finally:
            opts.close()


def test_set_visual_signature_from_path_as_string(tmp_path) -> None:
    pdf_path = tmp_path / "vis.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    with _patch_parser():
        opts = SignatureOptions()
        try:
            opts.set_visual_signature(str(pdf_path))
            assert opts.get_visual_signature() is not None
        finally:
            opts.close()


def test_set_visual_signature_from_binary_io() -> None:
    with _patch_parser():
        opts = SignatureOptions()
        try:
            handle = io.BytesIO(b"%PDF-1.4\n%%EOF\n")
            opts.set_visual_signature(handle)
            assert opts.get_visual_signature() is not None
            # The handle is what we passed in.
            assert _FakeParser.last_source is handle
        finally:
            opts.close()


def test_set_visual_signature_from_visible_sig_properties() -> None:
    """Objects exposing ``get_visible_signature`` forward to the stream
    overload (PDVisibleSigProperties duck-type)."""

    class FakeProps:
        def __init__(self, stream):
            self._stream = stream

        def get_visible_signature(self):
            return self._stream

    stream = io.BytesIO(b"%PDF-1.4\n%%EOF\n")
    with _patch_parser():
        opts = SignatureOptions()
        try:
            opts.set_visual_signature(FakeProps(stream))
            assert opts.get_visual_signature() is not None
            assert _FakeParser.last_source is stream
        finally:
            opts.close()


# ----------------------------------------------------------------------
# init_from_random_access_read
# ----------------------------------------------------------------------


class _StubRAR:
    """RandomAccessRead-like — exposes both ``length()`` and ``read(n)``."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def length(self) -> int:
        return len(self._data)

    def read(self, n: int) -> bytes:
        return self._data[:n]


def test_init_from_random_access_read_with_length_and_read() -> None:
    with _patch_parser():
        opts = SignatureOptions()
        try:
            opts.init_from_random_access_read(_StubRAR(b"%PDF-1.4\n%%EOF\n"))
            assert opts.get_visual_signature() is not None
            # The parser saw a BytesIO wrapping the read bytes.
            assert isinstance(_FakeParser.last_source, io.BytesIO)
        finally:
            opts.close()


def test_init_from_random_access_read_with_plain_stream() -> None:
    with _patch_parser():
        stream = io.BytesIO(b"%PDF-1.4\n%%EOF\n")
        opts = SignatureOptions()
        try:
            opts.init_from_random_access_read(stream)
            assert opts.get_visual_signature() is not None
            assert _FakeParser.last_source is stream
        finally:
            opts.close()


def test_init_from_random_access_read_rejects_non_stream_argument() -> None:
    opts = SignatureOptions()
    try:
        with pytest.raises(TypeError, match="binary stream"):
            opts.init_from_random_access_read(object())
    finally:
        opts.close()


# ----------------------------------------------------------------------
# close() / context manager
# ----------------------------------------------------------------------


def test_close_invokes_visual_signature_close_and_source_close() -> None:
    with _patch_parser():
        opts = SignatureOptions()
        opts.set_visual_signature(io.BytesIO(b"%PDF-1.4\n%%EOF\n"))

        vs = opts.get_visual_signature()
        # The internal source is the BytesIO we supplied (since it's the
        # handle passed straight to ``_init_from_input``).
        source = opts._pdf_source
        assert source is not None

        close_observer = MagicMock(wraps=source.close)
        source.close = close_observer  # type: ignore[method-assign]

        opts.close()
        vs.close.assert_called_once()
        close_observer.assert_called_once()


def test_close_is_safe_when_no_visual_signature_or_source_set() -> None:
    opts = SignatureOptions()
    # No exception on a bare close().
    opts.close()
    # Idempotent.
    opts.close()


def test_close_tolerates_object_without_close_method() -> None:
    opts = SignatureOptions()
    # ``object()`` lacks ``close``; the helper must skip silently.
    opts._visual_signature = object()  # type: ignore[assignment]
    opts._pdf_source = object()
    opts.close()  # must not raise


def test_context_manager_closes_on_exit() -> None:
    with _patch_parser():
        with SignatureOptions() as opts:
            opts.set_visual_signature(io.BytesIO(b"%PDF-1.4\n%%EOF\n"))
            vs = opts.get_visual_signature()
        # After __exit__, close was called on the wrapped doc.
        vs.close.assert_called_once()

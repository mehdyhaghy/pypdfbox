from __future__ import annotations

import io

import pytest

from pypdfbox import Loader
from pypdfbox.pdfparser import PDFParseError


def test_load_pdf_malformed_bytes_raise_oserror_with_parse_cause() -> None:
    with pytest.raises(OSError) as excinfo:
        Loader.load_pdf(b"not a pdf at all")

    assert isinstance(excinfo.value.__cause__, PDFParseError)
    # Wave 1497: a header-less buffer no longer fails eagerly at the header
    # scan. Mirroring upstream PDFParser.parse(boolean), a lenient load (the
    # Loader default) logs "Error: Header doesn't contain versioninfo" and
    # falls through to brute-force recovery; a buffer with NO recoverable
    # ``n g obj`` definitions then surfaces the rejection downstream (the
    # cause is still a PDFParseError).
    assert "no recoverable objects" in str(excinfo.value)


def test_load_pdf_rejects_non_callable_read_attribute_at_loader_boundary() -> None:
    class _HasReadAttribute:
        read = b"not callable"

    with pytest.raises(TypeError, match="Loader.load_pdf expected"):
        Loader.load_pdf(_HasReadAttribute())  # type: ignore[arg-type]


def test_load_pdf_rejects_text_streams_before_parser_boundary() -> None:
    with pytest.raises(TypeError, match="source stream must yield bytes"):
        Loader.load_pdf(io.StringIO("%PDF-1.7\n"))  # type: ignore[arg-type]

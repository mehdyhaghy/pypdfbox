"""Wave 172 — small parity additions on the BaseParser / COSParser cluster.

Covers:
    * ``BaseParser.MAX_RECURSION_DEPTH`` / ``MAX_LENGTH_LONG`` constants
    * ``BaseParser.read_string_number()`` digit-only helper
    * ``COSParser.PDF_HEADER`` / ``FDF_HEADER`` / default-version /
      keyword-marker constants
    * ``COSParser.parse_fdf_header()`` + ``has_pdf_header()`` /
      ``has_fdf_header()`` predicates
"""

from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser, PDFParseError
from pypdfbox.pdfparser.cos_parser import COSParser


def _bp(data: bytes) -> BaseParser:
    return BaseParser(RandomAccessReadBuffer(data))


def _cp(data: bytes) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data))


# ---------- BaseParser constants ----------


def test_base_parser_max_recursion_depth_constant() -> None:
    """Upstream BaseParser caps recursion at 500."""
    assert BaseParser.MAX_RECURSION_DEPTH == 500


def test_base_parser_max_length_long_constant() -> None:
    """Upstream MAX_LENGTH_LONG = len(str(Long.MAX_VALUE)) = 19."""
    assert BaseParser.MAX_LENGTH_LONG == 19


# ---------- read_string_number ----------


def test_read_string_number_returns_digit_only_token() -> None:
    p = _bp(b"12345 trailer")
    assert p.read_string_number() == "12345"
    # Cursor should be left at the space — peek rather than read so this
    # also doubles as a position check.
    assert p.peek_byte() == 0x20


def test_read_string_number_empty_at_non_digit() -> None:
    p = _bp(b"abc")
    assert p.read_string_number() == ""
    # Non-digit byte should still be unread.
    assert p.peek_byte() == ord("a")


def test_read_string_number_at_eof_returns_empty() -> None:
    p = _bp(b"")
    assert p.read_string_number() == ""


def test_read_string_number_consumes_all_digits_to_eof() -> None:
    p = _bp(b"42")
    assert p.read_string_number() == "42"
    assert p.is_eof()


def test_read_string_number_rejects_overlong_token() -> None:
    # 20 digits — one past MAX_LENGTH_LONG (19).
    p = _bp(b"1" * 25)
    with pytest.raises(PDFParseError, match="getting too long"):
        p.read_string_number()


# ---------- COSParser header / marker constants ----------


def test_cos_parser_pdf_header_constant() -> None:
    assert COSParser.PDF_HEADER == "%PDF-"


def test_cos_parser_fdf_header_constant() -> None:
    assert COSParser.FDF_HEADER == "%FDF-"


def test_cos_parser_default_version_constants() -> None:
    assert COSParser.PDF_DEFAULT_VERSION == "1.4"
    assert COSParser.FDF_DEFAULT_VERSION == "1.0"


def test_cos_parser_keyword_marker_constants() -> None:
    assert COSParser.XREF_TABLE_MARKER == b"xref"
    assert COSParser.STARTXREF_MARKER == b"startxref"
    assert COSParser.ENDSTREAM_MARKER == b"endstream"
    assert COSParser.ENDOBJ_MARKER == b"endobj"


def test_cos_parser_minimum_search_offset_and_strmbuflen() -> None:
    assert COSParser.MINIMUM_SEARCH_OFFSET == 6
    assert COSParser.STRMBUFLEN == 2048


# ---------- parse_fdf_header ----------


def test_parse_fdf_header_returns_version() -> None:
    p = _cp(b"%FDF-1.2\n%binary\n...rest of fdf...")
    assert p.parse_fdf_header() == 1.2


def test_parse_fdf_header_default_when_no_version_digits() -> None:
    """When marker is followed immediately by EOL, fall back to default."""
    p = _cp(b"%FDF-\n...")
    assert p.parse_fdf_header() == 1.0


def test_parse_fdf_header_raises_on_missing_marker() -> None:
    p = _cp(b"%PDF-1.4\n...")
    with pytest.raises(PDFParseError, match="missing %FDF-"):
        p.parse_fdf_header()


def test_parse_pdf_header_default_when_no_version_digits() -> None:
    """Same default-fallback behaviour for the PDF parser path."""
    p = _cp(b"%PDF-\n...")
    assert p.parse_pdf_header() == 1.4


def test_parse_pdf_header_tolerates_leading_garbage() -> None:
    """Producers sometimes prepend MIME envelopes / shebangs."""
    p = _cp(b"#!/usr/bin/env pdf\nMIME-Version: 1.0\n\n%PDF-1.7\n...")
    assert p.parse_pdf_header() == 1.7


# ---------- has_pdf_header / has_fdf_header ----------


def test_has_pdf_header_true_for_pdf() -> None:
    p = _cp(b"%PDF-1.4\n...")
    assert p.has_pdf_header() is True
    assert p.has_fdf_header() is False


def test_has_fdf_header_true_for_fdf() -> None:
    p = _cp(b"%FDF-1.2\n...")
    assert p.has_fdf_header() is True
    assert p.has_pdf_header() is False


def test_has_header_predicates_dont_advance_cursor() -> None:
    """Predicates must restore cursor position even on success."""
    p = _cp(b"%PDF-1.7\nrest")
    p.seek(3)
    saved = p.position
    assert p.has_pdf_header() is True
    assert p.position == saved
    assert p.has_fdf_header() is False
    assert p.position == saved


def test_has_header_predicates_false_for_garbage() -> None:
    p = _cp(b"not a pdf at all")
    assert p.has_pdf_header() is False
    assert p.has_fdf_header() is False

"""Wave 1581 — header (%PDF-/%FDF-) + startxref/%%EOF parse fuzzing.

Hammers :meth:`PDFParser.parse_header` / :meth:`parse_pdf_header`,
:meth:`COSParser.parse_header` (PDF + FDF markers), the
:meth:`find_startxref_offset` trailing-byte scan (last ``%%EOF`` anchoring,
last ``startxref`` wins), and the header-vs-catalog ``/Version`` override.

Behavioural oracle: PDFBox 3.0.7 ``COSParser.parseHeader`` /
``getStartxrefOffset`` (``pdfbox/src/main/java/org/apache/pdfbox/pdfparser/
COSParser.java``). Key upstream invariants exercised here:

  * version parse is ``Float.parseFloat`` of the digits after the marker;
  * garbage *after* the version on the same line is trimmed to ``x.y``;
  * a marker with NO version digits defaults to 1.4 (PDF) / 1.0 (FDF);
  * a *malformed* version is caught (NumberFormatException) → 1.7 in lenient
    mode, ``IOException`` only in strict mode;
  * up to 1024 bytes of leading garbage before the marker are tolerated;
  * ``getStartxrefOffset`` finds the LAST ``%%EOF`` then the LAST
    ``startxref`` PRECEDING it; a missing ``%%EOF`` raises in strict mode and
    is tolerated in lenient mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pypdfbox.cos import COSDocument, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser

if TYPE_CHECKING:
    from pypdfbox.pdmodel import PDDocument


def _pdf_parser(data: bytes, *, lenient: bool = True) -> PDFParser:
    p = PDFParser(RandomAccessReadBuffer(data))
    p.set_lenient(lenient)
    return p


def _cos_parser(data: bytes, *, lenient: bool = True) -> COSParser:
    p = COSParser(RandomAccessReadBuffer(data))
    p.set_lenient(lenient)
    return p


# --------------------------------------------------------------------------
# header version parse — %PDF-x.y
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (b"%PDF-1.0\n", 1.0),
        (b"%PDF-1.1\n", 1.1),
        (b"%PDF-1.2\n", 1.2),
        (b"%PDF-1.3\n", 1.3),
        (b"%PDF-1.4\n", 1.4),
        (b"%PDF-1.5\n", 1.5),
        (b"%PDF-1.6\n", 1.6),
        (b"%PDF-1.7\n", 1.7),
        (b"%PDF-2.0\n", 2.0),
    ],
    ids=[
        "1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "2.0",
    ],
)
def test_pdf_header_version_parse(header: bytes, expected: float) -> None:
    assert _pdf_parser(header + b"rest").parse_header() == expected
    assert _cos_parser(header + b"rest").parse_pdf_header() == expected


def test_header_version_carriage_return_terminator() -> None:
    # \r and \r\n both terminate the version digits (0x0D / 0x0A).
    assert _pdf_parser(b"%PDF-1.7\r\nrest").parse_header() == 1.7
    assert _pdf_parser(b"%PDF-1.7\rrest").parse_header() == 1.7


def test_header_version_space_terminator() -> None:
    # A space (0x20) terminates the version read too.
    assert _pdf_parser(b"%PDF-1.4 garbage\n").parse_header() == 1.4


# --------------------------------------------------------------------------
# leading junk before the marker
# --------------------------------------------------------------------------


def test_header_leading_junk_tolerated() -> None:
    # Upstream tolerates garbage before the marker (within 1024 bytes).
    data = b"#!/usr/bin/env nonsense\nMIME-junk\n%PDF-1.5\nrest"
    assert _pdf_parser(data).parse_header() == 1.5
    assert _cos_parser(data).parse_pdf_header() == 1.5


def test_header_leading_binary_junk_then_marker() -> None:
    data = b"\x00\x01\x02\xff\xfe%PDF-1.6\n"
    assert _pdf_parser(data).parse_header() == 1.6


def test_header_marker_just_inside_scan_window() -> None:
    # 1019 bytes of junk + "%PDF-2.0" keeps the 5-byte marker start at 1019,
    # well inside the 1024-byte scan window.
    data = b"x" * 1019 + b"%PDF-2.0\n"
    assert _pdf_parser(data).parse_header() == 2.0


def test_header_marker_pushed_past_scan_window_missing() -> None:
    # > 1024 bytes of junk pushes the marker out of the window → not found.
    data = b"x" * 1100 + b"%PDF-1.4\n"
    p = _pdf_parser(data, lenient=False)
    assert p.parse_pdf_header() is False


# --------------------------------------------------------------------------
# missing header
# --------------------------------------------------------------------------


def test_missing_header_pdf_parser_returns_false() -> None:
    # PDFParser.parse_pdf_header returns False (not raises) on a missing
    # marker — the boolean shape upstream COSParser.parsePDFHeader carries.
    assert _pdf_parser(b"no marker at all here").parse_pdf_header() is False


def test_missing_header_cos_predicate_false() -> None:
    # COSParser exposes the boolean predicate via has_pdf_header (parse_header
    # itself returns the float version, so it raises when no marker is found).
    assert _cos_parser(b"no marker at all here").has_pdf_header() is False


def test_missing_header_pdf_parser_lenient_false_return() -> None:
    # PDFParser.parse_pdf_header returns False (not raises) on a missing
    # marker; the strict/lenient decision is deferred to parse().
    assert _pdf_parser(b"not a pdf", lenient=False).parse_pdf_header() is False
    assert _pdf_parser(b"not a pdf", lenient=True).parse_pdf_header() is False


# --------------------------------------------------------------------------
# malformed version
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "header",
    [b"%PDF-X.Y\n", b"%PDF-bad\n", b"%PDF-abc\n", b"%PDF-..\n"],
    ids=["XY", "bad", "abc", "dots"],
)
def test_malformed_version_lenient_defaults_to_1_7(header: bytes) -> None:
    # Upstream: NumberFormatException caught → 1.7 in lenient mode.
    assert _pdf_parser(header, lenient=True).parse_header() == 1.7
    assert _cos_parser(header, lenient=True).parse_pdf_header() == 1.7


@pytest.mark.parametrize(
    "header",
    [b"%PDF-X.Y\n", b"%PDF-bad\n"],
    ids=["XY", "bad"],
)
def test_malformed_version_strict_raises(header: bytes) -> None:
    with pytest.raises(PDFParseError):
        _pdf_parser(header, lenient=False).parse_header()
    with pytest.raises(PDFParseError):
        _cos_parser(header, lenient=False).parse_pdf_header()


def test_empty_version_defaults_pdf_1_4() -> None:
    # No digits after the marker → upstream substitutes the 1.4 default for
    # %PDF- (this is the no-digits branch, NOT a malformed-version error).
    assert _pdf_parser(b"%PDF-\nrest").parse_header() == 1.4
    assert _cos_parser(b"%PDF-\nrest").parse_pdf_header() == 1.4


def test_trailing_garbage_after_version_trimmed() -> None:
    # %PDF-1.4FOO → upstream keeps marker + 3 chars (1.4) and rewinds the
    # rest; the version still parses as 1.4 rather than failing on "1.4FOO".
    assert _pdf_parser(b"%PDF-1.4FOO\n").parse_header() == 1.4
    assert _cos_parser(b"%PDF-1.4FOO\n").parse_pdf_header() == 1.4
    # %PDF-1.7xyz on the same line still yields 1.7.
    assert _pdf_parser(b"%PDF-1.7xyz\n").parse_header() == 1.7


# --------------------------------------------------------------------------
# FDF header — %FDF-1.2
# --------------------------------------------------------------------------


def test_fdf_header_version_parse() -> None:
    assert _pdf_parser(b"%FDF-1.2\nrest").parse_header() == 1.2
    assert _cos_parser(b"%FDF-1.2\nrest").parse_fdf_header() == 1.2


def test_fdf_header_empty_version_defaults_1_0() -> None:
    # FDF's no-digits default is 1.0 (distinct from PDF's 1.4).
    assert _pdf_parser(b"%FDF-\nrest").parse_header() == 1.0
    assert _cos_parser(b"%FDF-\nrest").parse_fdf_header() == 1.0


def test_fdf_malformed_version_lenient_1_7_not_1_0() -> None:
    # Malformed → 1.7 in lenient mode, NOT the FDF default 1.0.
    assert _cos_parser(b"%FDF-bad\n", lenient=True).parse_fdf_header() == 1.7


def test_fdf_header_via_pdf_parser_fallback() -> None:
    # PDFParser.parse_header accepts %FDF- when %PDF- is absent.
    assert _pdf_parser(b"%FDF-1.4\nrest").parse_header() == 1.4


# --------------------------------------------------------------------------
# startxref directive + offset
# --------------------------------------------------------------------------


def test_find_startxref_basic() -> None:
    data = b"%PDF-1.4\n<<body>>\nstartxref\n123\n%%EOF"
    assert _pdf_parser(data).find_startxref_offset(validate_bounds=False) == 123


def test_find_startxref_offset_on_following_line() -> None:
    data = b"%PDF-1.7\nstuff\nstartxref\n   4567\n%%EOF\n"
    assert _pdf_parser(data).find_startxref_offset(validate_bounds=False) == 4567


def test_find_startxref_last_wins() -> None:
    # Multiple startxref directives → the LAST one (preceding %%EOF) wins.
    data = (
        b"%PDF-1.5\n"
        b"startxref\n11\n%%EOF\n"
        b"startxref\n22\n%%EOF\n"
        b"startxref\n33\n%%EOF"
    )
    assert _pdf_parser(data).find_startxref_offset(validate_bounds=False) == 33


def test_find_startxref_anchored_before_last_eof() -> None:
    # A bogus "startxref" appearing AFTER the final %%EOF (in trailing junk)
    # must NOT be picked up — upstream anchors the lookup before %%EOF.
    data = (
        b"%PDF-1.4\nstartxref\n99\n%%EOF\n"
        b"trailing junk startxref 7777 more junk"
    )
    assert _pdf_parser(data).find_startxref_offset(validate_bounds=False) == 99


def test_find_startxref_eof_trailing_whitespace_tolerated() -> None:
    data = b"%PDF-1.4\nstartxref\n55\n%%EOF   \r\n\r\n"
    assert _pdf_parser(data).find_startxref_offset(validate_bounds=False) == 55


def test_find_startxref_eof_trailing_junk_after_marker() -> None:
    # Garbage bytes after the %%EOF marker still leave it the last %%EOF.
    data = b"%PDF-1.4\nstartxref\n42\n%%EOF\x00\x00\x00"
    assert _pdf_parser(data).find_startxref_offset(validate_bounds=False) == 42


def test_find_startxref_missing_eof_strict_raises() -> None:
    # Strict mode requires the %%EOF marker.
    data = b"%PDF-1.4\nstartxref\n12\n"
    with pytest.raises(PDFParseError):
        _pdf_parser(data, lenient=False).find_startxref_offset(
            validate_bounds=False
        )


def test_find_startxref_missing_eof_lenient_ok() -> None:
    # Lenient mode does not require %%EOF; startxref is still located.
    data = b"%PDF-1.4\nstartxref\n12\n"
    assert (
        _pdf_parser(data, lenient=True).find_startxref_offset(
            validate_bounds=False
        )
        == 12
    )


def test_find_startxref_missing_directive_raises() -> None:
    data = b"%PDF-1.4\nbody with no directive\n%%EOF"
    with pytest.raises(PDFParseError):
        _pdf_parser(data).find_startxref_offset(validate_bounds=False)


def test_find_startxref_offset_past_eof_strict_bounds_check() -> None:
    # An offset past EOF fails the bounds check when validate_bounds=True.
    data = b"%PDF-1.4\nstartxref\n999999\n%%EOF"
    with pytest.raises(PDFParseError):
        _pdf_parser(data).find_startxref_offset(validate_bounds=True)


def test_find_startxref_offset_past_eof_lenient_no_bounds() -> None:
    # With validate_bounds=False (the lenient parse path) a too-large offset
    # is returned as-is for downstream brute-force recovery to correct.
    data = b"%PDF-1.4\nstartxref\n999999\n%%EOF"
    assert (
        _pdf_parser(data).find_startxref_offset(validate_bounds=False)
        == 999999
    )


def test_find_startxref_honours_small_lookup_window() -> None:
    # A scan window smaller than the tail beyond the directive can't see it.
    data = b"%PDF-1.4\nstartxref\n7\n%%EOF" + b"Z" * 200
    p = _pdf_parser(data)
    # Window > 15 (upstream ignores <= 15) but smaller than the 200 trailing
    # bytes, so neither %%EOF nor startxref falls inside it.
    p.set_eof_lookup_range(20)
    with pytest.raises(PDFParseError):
        p.find_startxref_offset(validate_bounds=False)


def test_find_startxref_zero_offset() -> None:
    data = b"%PDF-1.4\nstartxref\n0\n%%EOF"
    assert _pdf_parser(data).find_startxref_offset(validate_bounds=True) == 0


# --------------------------------------------------------------------------
# version comparison — header vs catalog /Version override
# --------------------------------------------------------------------------


def _doc_with_catalog_version(
    header_version: float, catalog_version: str
) -> PDDocument:
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel import PDDocument

    doc = COSDocument()
    doc.set_version(header_version)
    cat = COSDictionary()
    cat.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))
    cat.set_item(
        COSName.get_pdf_name("Version"),
        COSName.get_pdf_name(catalog_version),
    )
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, cat)
    doc.set_trailer(trailer)
    return PDDocument(doc)


def test_catalog_version_override_above_1_4() -> None:
    # Header 1.4, catalog /Version /1.7 → effective 1.7 (max of the two).
    pd = _doc_with_catalog_version(1.4, "1.7")
    assert pd.get_version() == 1.7
    pd.close()


def test_catalog_version_ignored_when_header_below_1_4() -> None:
    # Per ISO 32000-1 §7.5.2 the catalog override is consulted ONLY when the
    # header is already >= 1.4. Header 1.3 + catalog 1.7 → stays 1.3.
    pd = _doc_with_catalog_version(1.3, "1.7")
    assert pd.get_version() == 1.3
    pd.close()


def test_catalog_version_lower_than_header_keeps_header() -> None:
    # Catalog /Version below the header version does not downgrade it.
    pd = _doc_with_catalog_version(1.7, "1.4")
    assert pd.get_version() == 1.7
    pd.close()


def test_catalog_malformed_version_falls_back_to_header() -> None:
    # A non-numeric catalog /Version is logged and skipped → header wins.
    pd = _doc_with_catalog_version(1.6, "bogus")
    assert pd.get_version() == 1.6
    pd.close()


# --------------------------------------------------------------------------
# end-to-end: parse a tiny well-formed PDF and read the version off the doc
# --------------------------------------------------------------------------


def _minimal_pdf(version: bytes) -> bytes:
    body = (
        b"%" + b"PDF-" + version + b"\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\n"
        b"endobj\n"
    )
    xref_off = len(body)
    xref = (
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
    )
    # entry offsets are not validated by the version check; use placeholders
    obj1 = body.index(b"1 0 obj")
    obj2 = body.index(b"2 0 obj")
    obj3 = body.index(b"3 0 obj")
    xref += (
        f"{obj1:010d} 00000 n \n".encode("ascii")
        + f"{obj2:010d} 00000 n \n".encode("ascii")
        + f"{obj3:010d} 00000 n \n".encode("ascii")
    )
    trailer = (
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    )
    return body + xref + trailer


def test_end_to_end_version_recorded_on_document() -> None:
    from pypdfbox.pdmodel import PDDocument

    for ver, expected in ((b"1.4", 1.4), (b"1.7", 1.7), (b"2.0", 2.0)):
        with PDDocument.load(_minimal_pdf(ver)) as doc:
            assert doc.get_version() == expected

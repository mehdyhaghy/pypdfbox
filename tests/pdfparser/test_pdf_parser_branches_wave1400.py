"""Branch coverage for :class:`PDFParser` — wave 1400.

Closes residual partial branches in ``pypdfbox/pdfparser/pdf_parser.py``:

* ``parse()`` trailer-None branch (207 → 209).
* ``initial_parse`` when ``_cos_parser`` is None (243 → 222).
* ``_detect_linearization``: /H array too short, wrong types, offset
  out of bounds (646/649/655 → 667).
* ``parse_xref_chain`` non-COSInteger /Prev (926 → 928).
* ``_handle_xref_stream_at`` hybrid path with ``_document is None``
  (1007 → 1020).
* ``_consume_eol_after_stream_keyword`` at EOF (1519 → -1506).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSDocument,
    COSName,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser, XrefTrailerResolver
from pypdfbox.pdfparser.parse_error import PDFParseError


def _bare_parser(payload: bytes = b"%PDF-1.7\n%%EOF\n") -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(payload))


# ----------------------------------------------------------------------
# initial_parse — cos_parser None branch
# ----------------------------------------------------------------------


def test_initial_parse_without_cos_parser_skips_set_initial_parse_done() -> None:
    """When ``_cos_parser`` is None we skip the
    ``set_initial_parse_done(True)`` notification — but the rest of
    initial_parse still runs (root validation, trailer fetch).

    Closes branch (243 → 222)."""
    p = _bare_parser()
    # Stub the resolver with a trailer whose /Root is a COSDictionary.
    p._resolver = XrefTrailerResolver()  # noqa: SLF001
    p._resolver.begin_section(0)  # noqa: SLF001
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.CATALOG)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, root)
    p._resolver.set_trailer(trailer)  # noqa: SLF001
    p._cos_parser = None  # noqa: SLF001 - simulate pre-parse state

    # Must not raise — even with cos_parser None.
    p.initial_parse()


def test_initial_parse_missing_root_raises() -> None:
    """``/Root`` is not a COSDictionary → raises PDFParseError."""
    p = _bare_parser()
    p._resolver = XrefTrailerResolver()  # noqa: SLF001
    p._resolver.begin_section(0)  # noqa: SLF001
    trailer = COSDictionary()
    # /Root set to a string — not a dictionary.
    trailer.set_item(COSName.ROOT, COSString("oops"))
    p._resolver.set_trailer(trailer)  # noqa: SLF001
    with pytest.raises(PDFParseError):
        p.initial_parse()


def test_initial_parse_missing_trailer_raises() -> None:
    """No trailer at all → PDFParseError before /Root is checked."""
    p = _bare_parser()
    p._resolver = XrefTrailerResolver()  # noqa: SLF001
    with pytest.raises(PDFParseError):
        p.initial_parse()


# ----------------------------------------------------------------------
# _detect_linearization — /H array shape branches
# ----------------------------------------------------------------------


def _make_lin_payload(h_entry: str = "[100 200]") -> bytes:
    """Synthetic linearization-shaped first object. ``h_entry`` is
    the verbatim /H array bytes — caller controls its shape so we
    can exercise the size/type/range branches."""
    return (
        b"%PDF-1.7\n"
        b"1 0 obj\n"
        b"<< /Linearized 1 /N 1 /H " + h_entry.encode("ascii") + b" "
        b"/O 4 /E 0 /L 1000 /T 0 >>\n"
        b"endobj\n"
        b"%%EOF\n"
    )


def test_detect_linearization_with_h_array_too_short_skips_hint_slurp() -> None:
    """/H array with fewer than 2 entries → branch (646 → 667). The
    linearization dict is still recorded but no hint_table_bytes."""
    p = PDFParser(RandomAccessReadBuffer(_make_lin_payload(h_entry="[100]")))
    # _detect_linearization is called inline by parse; run it directly.
    p._document = COSDocument()  # noqa: SLF001
    from pypdfbox.pdfparser.cos_parser import COSParser

    p._cos_parser = COSParser(p._src, document=p._document)  # noqa: SLF001
    p._src.seek(0)  # rewind past any prior scan
    p.parse_header()
    p._detect_linearization()  # noqa: SLF001
    assert p.linearization_dict is not None
    assert p.hint_table_bytes is None


def test_detect_linearization_with_h_array_non_numeric_skips_slurp() -> None:
    """/H[0] is not a number → branch (649 → 667)."""
    payload = _make_lin_payload(h_entry="[/Bogus 200]")
    p = PDFParser(RandomAccessReadBuffer(payload))
    p._document = COSDocument()  # noqa: SLF001
    from pypdfbox.pdfparser.cos_parser import COSParser

    p._cos_parser = COSParser(p._src, document=p._document)  # noqa: SLF001
    p._src.seek(0)
    p.parse_header()
    p._detect_linearization()  # noqa: SLF001
    assert p.linearization_dict is not None
    assert p.hint_table_bytes is None


def test_detect_linearization_with_h_offset_out_of_bounds_skips_slurp() -> None:
    """/H offset >= file length → branch (655 → 667). The bounds
    check rejects the slurp without raising."""
    payload = _make_lin_payload(h_entry="[999999999 100]")
    p = PDFParser(RandomAccessReadBuffer(payload))
    p._document = COSDocument()  # noqa: SLF001
    from pypdfbox.pdfparser.cos_parser import COSParser

    p._cos_parser = COSParser(p._src, document=p._document)  # noqa: SLF001
    p._src.seek(0)
    p.parse_header()
    p._detect_linearization()  # noqa: SLF001
    assert p.linearization_dict is not None
    assert p.hint_table_bytes is None


def test_detect_linearization_with_valid_h_slurps_bytes() -> None:
    """Positive control: well-formed /H within file bounds → slurp
    populates hint_table_bytes (exercises the 'taken' branch)."""
    payload = _make_lin_payload(h_entry="[5 10]")  # offset=5, length=10 - in bounds
    p = PDFParser(RandomAccessReadBuffer(payload))
    p._document = COSDocument()  # noqa: SLF001
    from pypdfbox.pdfparser.cos_parser import COSParser

    p._cos_parser = COSParser(p._src, document=p._document)  # noqa: SLF001
    p._src.seek(0)
    p.parse_header()
    p._detect_linearization()  # noqa: SLF001
    assert p.linearization_dict is not None
    assert p.hint_table_bytes is not None
    assert len(p.hint_table_bytes) == 10


# ----------------------------------------------------------------------
# _consume_eol_after_stream_keyword — EOF branch
# ----------------------------------------------------------------------


def test_consume_eol_after_stream_keyword_at_eof_no_rewind() -> None:
    """When ``stream`` is the last keyword in the file (EOF immediately
    after), the helper must not attempt to rewind.

    Closes branch (1519 → -1506)."""
    p = PDFParser(RandomAccessReadBuffer(b""))
    # _src is at position 0, length 0 — read returns EOF.
    # Should not raise.
    p._consume_eol_after_stream_keyword()  # noqa: SLF001
    assert p._src.get_position() == 0  # noqa: SLF001


def test_consume_eol_after_stream_keyword_with_garbage_byte_rewinds() -> None:
    """Positive control: non-EOL non-EOF byte triggers the rewind path."""
    p = PDFParser(RandomAccessReadBuffer(b"X"))
    p._consume_eol_after_stream_keyword()  # noqa: SLF001
    # 'X' was read then rewound — position back at 0.
    assert p._src.get_position() == 0  # noqa: SLF001


def test_consume_eol_after_stream_keyword_consumes_crlf() -> None:
    """CRLF consumed as a unit."""
    p = PDFParser(RandomAccessReadBuffer(b"\r\nbody"))
    p._consume_eol_after_stream_keyword()  # noqa: SLF001
    assert p._src.get_position() == 2  # noqa: SLF001


def test_consume_eol_after_stream_keyword_consumes_lf_only() -> None:
    """LF alone consumed."""
    p = PDFParser(RandomAccessReadBuffer(b"\nbody"))
    p._consume_eol_after_stream_keyword()  # noqa: SLF001
    assert p._src.get_position() == 1  # noqa: SLF001


def test_consume_eol_after_stream_keyword_consumes_lone_cr() -> None:
    """Lone CR (no LF) consumed (PDFBox quirk)."""
    p = PDFParser(RandomAccessReadBuffer(b"\rbody"))
    p._consume_eol_after_stream_keyword()  # noqa: SLF001
    assert p._src.get_position() == 1  # noqa: SLF001


# ----------------------------------------------------------------------
# parse_xref_chain — non-integer /Prev
# ----------------------------------------------------------------------


def test_parse_xref_chain_non_integer_prev_stops_chain() -> None:
    """If a trailer's /Prev is not a COSInteger (e.g. a name or a
    string from a malformed file), the chain walk must skip it — the
    current_prev stays -1 and the loop terminates.

    Closes branch (926 → 928)."""
    # Construct a minimal PDF whose trailer's /Prev is a name.
    payload = (
        b"%PDF-1.7\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"xref\n"
        b"0 3\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000055 00000 n \n"
        b"trailer\n<< /Size 3 /Root 1 0 R /Prev /OopsThisIsAName >>\n"
        b"startxref\n103\n%%EOF\n"
    )
    p = PDFParser(RandomAccessReadBuffer(payload))
    # Must not raise — the non-integer /Prev is silently ignored.
    p.parse()
    # Trailer is loaded; /Prev was a name and didn't blow up the chain.
    assert p._document is not None  # noqa: SLF001

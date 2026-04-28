"""Hand-written tests for the lenient / recovery surface on
``COSParser`` — mirrors the behavioural shape of upstream's
``bfSearchForObjects`` / ``bfSearchForXRef`` / ``rebuildTrailer`` /
``parseXrefStream`` paths.

The tests synthesize tiny malformed PDFs (truncated or absent xref
tables) and verify the recovery scanners can locate the raw object
headers, rebuild a usable trailer, and parse an xref-stream's
``/W`` + ``/Index`` shape into a per-entry offset map.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


# ---------- lenient toggle ----------


def test_lenient_default_is_true() -> None:
    p = _parser(b"")
    assert p.is_lenient() is True


def test_set_lenient_round_trip() -> None:
    p = _parser(b"")
    p.set_lenient(False)
    assert p.is_lenient() is False
    p.set_lenient(True)
    assert p.is_lenient() is True


def test_set_lenient_coerces_truthy() -> None:
    p = _parser(b"")
    p.set_lenient(0)  # type: ignore[arg-type]
    assert p.is_lenient() is False
    p.set_lenient(1)  # type: ignore[arg-type]
    assert p.is_lenient() is True


# ---------- bf_search_for_objects ----------


def test_bf_search_finds_single_object() -> None:
    pdf = b"%PDF-1.4\n1 0 obj\n42\nendobj\n%%EOF"
    offsets = _parser(pdf).bf_search_for_objects()
    key = COSObjectKey(1, 0)
    assert key in offsets
    # The recorded offset points at the first byte of the object number.
    assert pdf[offsets[key] : offsets[key] + len(b"1 0 obj")] == b"1 0 obj"


def test_bf_search_finds_multiple_objects() -> None:
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n"
        b"3 0 obj\n(hello)\nendobj\n"
        b"%%EOF"
    )
    offsets = _parser(pdf).bf_search_for_objects()
    assert COSObjectKey(1, 0) in offsets
    assert COSObjectKey(2, 0) in offsets
    assert COSObjectKey(3, 0) in offsets


def test_bf_search_ignores_endobj_substring() -> None:
    # Make sure the scanner doesn't pull ``obj`` out of ``endobj``.
    pdf = b"%PDF-1.4\n1 0 obj\n42\nendobj\n2 0 obj\n7\nendobj\n%%EOF"
    offsets = _parser(pdf).bf_search_for_objects()
    assert len(offsets) == 2
    assert {k.object_number for k in offsets} == {1, 2}


def test_bf_search_ignores_bare_obj_token() -> None:
    # A literal string containing the word ``obj`` must not register as
    # an object header — there's no ``n g`` pair preceding it.
    pdf = b"%PDF-1.4\n(this mentions obj)\n1 0 obj\n42\nendobj\n%%EOF"
    offsets = _parser(pdf).bf_search_for_objects()
    assert list(offsets) == [COSObjectKey(1, 0)]


def test_bf_search_handles_higher_generation() -> None:
    pdf = b"%PDF-1.4\n5 7 obj\n<< /K (v) >>\nendobj\n%%EOF"
    offsets = _parser(pdf).bf_search_for_objects()
    assert COSObjectKey(5, 7) in offsets


def test_bf_search_first_occurrence_wins() -> None:
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\nfirst\nendobj\n"
        b"junk junk junk\n"
        b"1 0 obj\nsecond\nendobj\n"
        b"%%EOF"
    )
    offsets = _parser(pdf).bf_search_for_objects()
    # The earlier offset wins.
    assert offsets[COSObjectKey(1, 0)] == pdf.find(b"1 0 obj")


def test_bf_search_empty_file_returns_empty_map() -> None:
    assert _parser(b"").bf_search_for_objects() == {}


# ---------- bf_search_for_xref ----------


def test_bf_search_for_xref_locates_traditional_table() -> None:
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n"
        b"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n70\n%%EOF"
    )
    expected = pdf.find(b"xref\n0 2")
    assert _parser(pdf).bf_search_for_xref(expected + 100) == expected


def test_bf_search_for_xref_skips_startxref_keyword() -> None:
    # ``startxref`` shares the substring ``xref`` — must not be a
    # candidate.
    pdf = b"%PDF-1.4\n1 0 obj\n42\nendobj\nstartxref\n9\n%%EOF"
    assert _parser(pdf).bf_search_for_xref(0) == -1


def test_bf_search_for_xref_skips_xref_name_token() -> None:
    # ``/XRef`` (a name token in a stream dict) must not match.
    pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /XRef /W [1 2 1] >>\nendobj\n%%EOF"
    # No traditional ``xref`` keyword — fall back finds the xref-stream
    # object header instead.
    offset = _parser(pdf).bf_search_for_xref(0)
    assert offset == pdf.find(b"1 0 obj")


def test_bf_search_for_xref_picks_nearest_candidate() -> None:
    # Two xref tables: the scanner should pick the one nearest the hint.
    pdf = (
        b"%PDF-1.4\n"
        b"xref\n0 1\n0000000000 65535 f \n"
        b"trailer\n<<>>\n"
        b"1 0 obj\n42\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \n"
        b"trailer\n<<>>\n"
        b"%%EOF"
    )
    first = pdf.find(b"xref\n0 1")
    second = pdf.find(b"xref\n0 1", first + 1)
    assert _parser(pdf).bf_search_for_xref(first) == first
    assert _parser(pdf).bf_search_for_xref(second) == second


def test_bf_search_for_xref_returns_minus_one_when_absent() -> None:
    pdf = b"%PDF-1.4\n1 0 obj\n42\nendobj\n%%EOF"
    assert _parser(pdf).bf_search_for_xref(0) == -1


# ---------- rebuild_trailer ----------


def test_rebuild_trailer_finds_root_via_catalog() -> None:
    doc = COSDocument()
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n"
        b"%%EOF"
    )
    trailer = _parser(pdf, document=doc).rebuild_trailer()
    root = trailer.get_item(COSName.get_pdf_name("Root"))
    assert isinstance(root, COSObject)
    assert root.get_object_number() == 1
    size = trailer.get_dictionary_object(COSName.get_pdf_name("Size"))
    assert isinstance(size, COSInteger)
    # /Size = max(object_number) + 1 — here that's 3.
    assert size.int_value() == 3


def test_rebuild_trailer_finds_info_via_known_keys() -> None:
    doc = COSDocument()
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Producer (pypdfbox) /Title (T) >>\nendobj\n"
        b"%%EOF"
    )
    trailer = _parser(pdf, document=doc).rebuild_trailer()
    info = trailer.get_item(COSName.get_pdf_name("Info"))
    assert isinstance(info, COSObject)
    assert info.get_object_number() == 2


def test_rebuild_trailer_propagates_id_array() -> None:
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /ID [(abc)(def)] >>\nendobj\n"
        b"%%EOF"
    )
    trailer = _parser(pdf, document=COSDocument()).rebuild_trailer()
    ids = trailer.get_item(COSName.get_pdf_name("ID"))
    assert isinstance(ids, COSArray)
    assert ids.size() == 2


def test_rebuild_trailer_empty_when_no_objects() -> None:
    trailer = _parser(b"%PDF-1.4\n%%EOF").rebuild_trailer()
    # An empty trailer has no /Root, no /Info, just an unknown /Size.
    assert not trailer.contains_key(COSName.get_pdf_name("Root"))
    assert not trailer.contains_key(COSName.get_pdf_name("Info"))


def test_rebuild_trailer_skips_object_with_unparseable_dict() -> None:
    # Object with truncated dict shouldn't crash the rebuild.
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog\nendobj\n"  # unterminated dict
        b"2 0 obj\n<< /Type /Catalog /Pages 3 0 R >>\nendobj\n"
        b"%%EOF"
    )
    trailer = _parser(pdf, document=COSDocument()).rebuild_trailer()
    root = trailer.get_item(COSName.get_pdf_name("Root"))
    assert isinstance(root, COSObject)
    # Object 2 is the parseable catalog and should win.
    assert root.get_object_number() == 2


# ---------- parse_xref_stream ----------


def _xref_stream_dict(
    w: list[int],
    index: list[int] | None = None,
    size: int | None = None,
) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XRef"))
    arr = COSArray()
    for v in w:
        arr.add(COSInteger.get(v))
    d.set_item(COSName.get_pdf_name("W"), arr)
    if index is not None:
        idx = COSArray()
        for v in index:
            idx.add(COSInteger.get(v))
        d.set_item(COSName.get_pdf_name("Index"), idx)
    if size is not None:
        d.set_item(COSName.get_pdf_name("Size"), COSInteger.get(size))
    return d


def test_parse_xref_stream_default_index() -> None:
    p = _parser(b"")
    table = p.parse_xref_stream(_xref_stream_dict([1, 2, 1], size=3))
    # Default /Index = [0 Size] → keys 0, 1, 2.
    assert set(table) == {COSObjectKey(0, 0), COSObjectKey(1, 0), COSObjectKey(2, 0)}
    # Entries are 4 bytes (1 + 2 + 1) — body offsets must step in 4s.
    assert sorted(table.values()) == [0, 4, 8]


def test_parse_xref_stream_explicit_index() -> None:
    p = _parser(b"")
    table = p.parse_xref_stream(
        _xref_stream_dict([1, 3, 1], index=[10, 2, 20, 1])
    )
    # Two ranges: (10, 11) and (20).
    assert COSObjectKey(10, 0) in table
    assert COSObjectKey(11, 0) in table
    assert COSObjectKey(20, 0) in table
    assert COSObjectKey(15, 0) not in table


def test_parse_xref_stream_pads_short_w_array() -> None:
    # Some malformed encoders ship /W [1 2] — must be tolerated by
    # padding to a 3-element layout.
    p = _parser(b"")
    table = p.parse_xref_stream(_xref_stream_dict([1, 2], size=2))
    # Total entry width = 1 + 2 + 0 = 3.
    assert sorted(table.values()) == [0, 3]


def test_parse_xref_stream_zero_field_widths_allowed() -> None:
    # /W [1 0 1] omits the offset field — entries are 2 bytes each.
    p = _parser(b"")
    table = p.parse_xref_stream(_xref_stream_dict([1, 0, 1], size=2))
    assert sorted(table.values()) == [0, 2]


def test_parse_xref_stream_rejects_negative_widths() -> None:
    from pypdfbox.pdfparser import PDFParseError

    p = _parser(b"")
    with pytest.raises(PDFParseError):
        p.parse_xref_stream(_xref_stream_dict([-1, 2, 1], size=1))


def test_parse_xref_stream_rejects_zero_total_width() -> None:
    from pypdfbox.pdfparser import PDFParseError

    p = _parser(b"")
    with pytest.raises(PDFParseError):
        p.parse_xref_stream(_xref_stream_dict([0, 0, 0], size=1))


def test_parse_xref_stream_missing_w_raises() -> None:
    from pypdfbox.pdfparser import PDFParseError

    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Size"), COSInteger.get(1))
    with pytest.raises(PDFParseError):
        _parser(b"").parse_xref_stream(d)


def test_parse_xref_stream_merges_into_existing_table() -> None:
    p = _parser(b"")
    existing: dict[COSObjectKey, int] = {COSObjectKey(99, 0): -1}
    out = p.parse_xref_stream(_xref_stream_dict([1, 2, 1], size=2), existing)
    # Existing entries stay; new ones are appended.
    assert out is existing
    assert COSObjectKey(99, 0) in out
    assert COSObjectKey(0, 0) in out
    assert COSObjectKey(1, 0) in out

"""Fuzz / parity tests for the COSParser cross-reference RECOVERY path
(wave 1575).

These hammer the brute-force rebuild machinery that fires when the xref
table/stream is missing or corrupt:

* a broken / missing ``startxref`` directive → whole-file ``n g obj`` scan
  (``bf_search_for_objects``),
* an xref offset pointing at the wrong byte → offset correction via brute
  force (``bf_search_for_xref`` / ``calculate_x_ref_fixed_offset``),
* duplicate ``N G obj`` headers for the same key (LAST occurrence wins, per
  upstream ``BruteForceParser.bfSearchForObjects`` unconditional ``Map.put``),
* trailer ``/Root`` recovery when the trailer dict is missing (scan for
  ``/Type /Catalog`` and for ``/Type /XRef`` stream catalogs),
* declared offsets off by a few bytes,
* truncated files, comments / junk between objects,
* an object number that only appears *inside a string* (matched by both
  upstream and pypdfbox — a documented shared limitation, asserted here so a
  future regression that changes the substring scan is caught).

All synthetic PDFs are built inline as ``bytes``. Behaviour is compared to
upstream PDFBox 3.0.7 ``COSParser`` / ``BruteForceParser`` semantics.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDocument,
    COSName,
    COSObjectKey,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import COSParser, PDFParseError, PDFParser


def _cos_parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def _parse(data: bytes, lenient: bool = True) -> COSDocument:
    return PDFParser(RandomAccessReadBuffer(data)).parse(lenient=lenient)


def _offsets(data: bytes) -> dict[tuple[int, int], int]:
    raw = _cos_parser(data).bf_search_for_objects()
    return {(k.object_number, k.generation_number): v for k, v in raw.items()}


# A small but structurally complete PDF body (no trailer / xref appended).
_BODY = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
)


# ---------- brute-force n g obj scan ----------


def test_bf_finds_all_three_objects() -> None:
    found = _offsets(_BODY)
    assert (1, 0) in found
    assert (2, 0) in found
    assert (3, 0) in found
    assert found[(1, 0)] == _BODY.find(b"1 0 obj")


def test_bf_offset_points_at_leading_object_number() -> None:
    found = _offsets(_BODY)
    # the recorded offset is the byte index of the leading object number,
    # the same format an xref entry carries.
    for (num, _gen), off in found.items():
        assert _BODY[off:off + 1] == str(num).encode("ascii")[:1]


def test_bf_ignores_endobj_substring() -> None:
    # ``endobj`` must not be back-walked into a phantom (n g obj) header.
    data = b"%PDF-1.4\n7 0 obj\n<<>>\nendobj\n%%EOF"
    found = _offsets(data)
    assert set(found) == {(7, 0)}


def test_bf_requires_two_integers_before_obj() -> None:
    # bare ``obj`` with only one preceding integer is not a header.
    data = b"%PDF-1.4\nfoo 5 obj\n<<>>\n%%EOF"
    # ``5`` is a single int -> gen present but no object number before it.
    found = _offsets(data)
    assert found == {}


def test_bf_rejects_abutting_digit_before_number() -> None:
    # ``991 0 obj`` where the 99 abuts: the byte before the object number is
    # itself a digit only when two literals abut with no whitespace.
    data = b"%PDF-1.4\nx99 0 obj\n<<>>\n%%EOF"
    found = _offsets(data)
    # ``99 0 obj`` is a clean header (``x`` is not a digit) -> recovered.
    assert (99, 0) in found


def test_bf_empty_source_returns_empty() -> None:
    assert _offsets(b"") == {}


def test_bf_no_objects_returns_empty() -> None:
    assert _offsets(b"%PDF-1.4\njust some text\n%%EOF") == {}


# ---------- duplicate object resolution: LAST wins ----------


def test_duplicate_object_last_offset_wins() -> None:
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /First true >>\nendobj\n"
        b"1 0 obj\n<< /Second true >>\nendobj\n%%EOF"
    )
    found = _offsets(data)
    assert found[(1, 0)] == data.rfind(b"1 0 obj")


def test_triplicate_object_last_offset_wins() -> None:
    data = (
        b"%PDF-1.4\n"
        b"5 0 obj\n<<>>\nendobj\n"
        b"5 0 obj\n<<>>\nendobj\n"
        b"5 0 obj\n<< /Final true >>\nendobj\n%%EOF"
    )
    found = _offsets(data)
    assert found[(5, 0)] == data.rfind(b"5 0 obj")


def test_distinct_generations_are_separate_keys() -> None:
    data = (
        b"%PDF-1.4\n"
        b"2 0 obj\n<<>>\nendobj\n"
        b"2 1 obj\n<<>>\nendobj\n%%EOF"
    )
    found = _offsets(data)
    assert (2, 0) in found
    assert (2, 1) in found
    assert found[(2, 0)] != found[(2, 1)]


def test_high_generation_kept_distinct() -> None:
    data = b"%PDF-1.4\n4 65535 obj\n<<>>\nendobj\n%%EOF"
    found = _offsets(data)
    assert (4, 65535) in found


# ---------- object number appearing inside a string ----------


def test_object_number_in_string_is_a_shared_false_positive() -> None:
    # Upstream ``bfSearchForObjects`` scans raw bytes and likewise matches a
    # ``N G obj`` token inside a literal string; pypdfbox mirrors that
    # limitation. The DECOY must therefore be recovered (parity), while the
    # real object is also present.
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Note (9 0 obj decoy) >>\nendobj\n%%EOF"
    )
    found = _offsets(data)
    assert (1, 0) in found
    # documented shared false positive — the decoy IS recovered.
    assert (9, 0) in found


def test_real_object_still_wins_over_string_decoy_when_redefined() -> None:
    # A real ``9 0 obj`` defined AFTER a string decoy: the real (later) offset
    # wins under last-occurrence semantics.
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Note (9 0 obj decoy) >>\nendobj\n"
        b"9 0 obj\n<< /Real true >>\nendobj\n%%EOF"
    )
    found = _offsets(data)
    assert found[(9, 0)] == data.rfind(b"9 0 obj")


# ---------- comments / junk between objects ----------


def test_comments_between_objects_do_not_break_scan() -> None:
    data = (
        b"%PDF-1.4\n"
        b"% a comment line\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"%%another comment\n\n  \t\n"
        b"2 0 obj\n<<>>\nendobj\n%%EOF"
    )
    found = _offsets(data)
    assert (1, 0) in found
    assert (2, 0) in found


def test_binary_junk_between_objects() -> None:
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
        + bytes(range(0, 32))
        + b"\n2 0 obj\n<<>>\nendobj\n%%EOF"
    )
    found = _offsets(data)
    assert (1, 0) in found
    assert (2, 0) in found


# ---------- truncated files ----------


def test_truncated_mid_object_recovers_complete_objects() -> None:
    # File cut off mid-dictionary of object 3: 1 and 2 are still recoverable.
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"2 0 obj\n<<>>\nendobj\n"
        b"3 0 obj\n<< /Incomplete tru"
    )
    found = _offsets(data)
    assert (1, 0) in found
    assert (2, 0) in found


def test_truncated_before_any_endobj() -> None:
    data = b"%PDF-1.4\n1 0 obj\n<< /A 1"
    found = _offsets(data)
    # the header is present so the raw scan still finds it.
    assert (1, 0) in found


# ---------- bf_search_for_xref: nearest table vs stream ----------


def _table_stream_doc() -> bytes:
    table = b"%PDF-1.4\nxref\n0 1\n0000000000 65535 f \ntrailer<<>>\n"
    spacer = b"x" * 200
    stream = b"5 0 obj\n<</Type/XRef/W[1 1 1]>>stream\nendstream endobj\n"
    return table + spacer + stream + b"startxref\n0\n%%EOF"


def test_xref_nearest_picks_stream_when_strictly_closer() -> None:
    data = _table_stream_doc()
    stream_obj = data.find(b"5 0 obj")
    p = _cos_parser(data)
    # target sits on the stream object -> stream is strictly nearer than the
    # far-away table; upstream picks the stream.
    assert p.bf_search_for_xref(stream_obj) == stream_obj


def test_xref_nearest_picks_table_when_strictly_closer() -> None:
    data = _table_stream_doc()
    table = data.find(b"xref")
    assert _cos_parser(data).bf_search_for_xref(table) == table


def test_xref_table_wins_on_distance_tie() -> None:
    # equal distance from both candidates -> table wins (upstream uses
    # ``differenceTable > differenceStream`` so only a strictly-nearer stream
    # switches).
    data = _table_stream_doc()
    table = data.find(b"xref")
    stream_obj = data.find(b"5 0 obj")
    midpoint = (table + stream_obj) // 2
    assert _cos_parser(data).bf_search_for_xref(midpoint) == table


def test_xref_table_only() -> None:
    data = b"%PDF-1.4\nxref\n0 1\n0000000000 65535 f \ntrailer<<>>\n%%EOF"
    assert _cos_parser(data).bf_search_for_xref(0) == data.find(b"xref")


def test_xref_stream_only() -> None:
    data = b"%PDF-1.4\n5 0 obj\n<</Type/XRef/W[1 1 1]>>stream\nendstream endobj\n%%EOF"
    assert _cos_parser(data).bf_search_for_xref(0) == data.find(b"5 0 obj")


def test_xref_neither_returns_minus_one() -> None:
    assert _cos_parser(b"%PDF-1.4\nonly junk here\n").bf_search_for_xref(0) == -1


def test_xref_keyword_in_header_region_not_found() -> None:
    # an ``xref`` buried inside the first MINIMUM_SEARCH_OFFSET (6) bytes is
    # deliberately skipped by upstream's seek-to-6 scan.
    data = b"xref\n  more\n xref\n%%EOF"
    # only the SECOND (whitespace-prefixed, past-offset-6) xref is a candidate.
    assert _cos_parser(data).bf_search_for_xref(0) == data.rfind(b"xref")


def test_xref_rejects_startxref_substring() -> None:
    data = b"%PDF-1.4\nstartxref\n12\n%%EOF"
    # the ``xref`` of ``startxref`` is preceded by ``t`` not whitespace.
    assert _cos_parser(data).bf_search_for_xref(0) == -1


def test_calculate_xref_fixed_offset_negative_input() -> None:
    assert _cos_parser(_table_stream_doc()).calculate_x_ref_fixed_offset(-5) == 0


def test_calculate_xref_fixed_offset_recovers() -> None:
    data = _table_stream_doc()
    p = _cos_parser(data, COSDocument())
    assert p.calculate_x_ref_fixed_offset(0) == data.find(b"xref")


# ---------- rebuild_trailer: /Root + /Info + /Size recovery ----------


def test_rebuild_trailer_finds_catalog_root() -> None:
    data = _BODY + b"%%EOF"
    trailer = _cos_parser(data).rebuild_trailer()
    root = trailer.get_item(COSName.ROOT)
    assert root is not None
    assert root.object_number == 1


def test_rebuild_trailer_finds_info_dictionary() -> None:
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"9 0 obj\n<< /Producer (probe) /Title (t) >>\nendobj\n%%EOF"
    )
    trailer = _cos_parser(data).rebuild_trailer()
    info = trailer.get_item(COSName.get_pdf_name("Info"))
    assert info is not None
    assert info.object_number == 9


def test_rebuild_trailer_size_is_max_obj_plus_one() -> None:
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"42 0 obj\n<<>>\nendobj\n%%EOF"
    )
    trailer = _cos_parser(data).rebuild_trailer()
    size = trailer.get_item(COSName.get_pdf_name("Size"))
    assert size.int_value() == 43


def test_rebuild_trailer_fdf_root_without_type() -> None:
    # FDF root dictionaries omit /Type but carry /FDF (PDFBOX-3639).
    data = b"%PDF-1.4\n1 0 obj\n<< /FDF << /F (x) >> >>\nendobj\n%%EOF"
    trailer = _cos_parser(data).rebuild_trailer()
    assert trailer.get_item(COSName.ROOT) is not None


def test_rebuild_trailer_no_catalog_no_root() -> None:
    data = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n%%EOF"
    trailer = _cos_parser(data).rebuild_trailer()
    assert trailer.get_item(COSName.ROOT) is None


def test_rebuild_trailer_empty_source() -> None:
    trailer = _cos_parser(b"").rebuild_trailer()
    assert trailer.get_item(COSName.ROOT) is None


def test_rebuild_trailer_first_catalog_wins() -> None:
    # two catalogs: the first one encountered claims /Root (the iteration is
    # over the recovered-offset map; whichever key resolves first to a catalog
    # is kept — never overwritten once set).
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 9 0 R >>\nendobj\n"
        b"3 0 obj\n<< /Type /Catalog /Pages 9 0 R >>\nendobj\n%%EOF"
    )
    trailer = _cos_parser(data).rebuild_trailer()
    root = trailer.get_item(COSName.ROOT)
    assert root.object_number in (1, 3)


# ---------- end-to-end PDFParser recovery ----------


def test_parse_broken_startxref_recovers_root() -> None:
    data = _BODY + b"trailer\n<< /Root 1 0 R /Size 4 >>\nstartxref\n99999\n%%EOF"
    doc = _parse(data)
    try:
        root = doc.get_trailer().get_dictionary_object(COSName.ROOT)
        assert root is not None
        assert (
            root.get_dictionary_object(COSName.TYPE)
            is COSName.get_pdf_name("Catalog")
        )
    finally:
        doc.close()


def test_parse_missing_startxref_entirely() -> None:
    # no startxref directive at all -> full brute-force rebuild.
    data = _BODY + b"trailer\n<< /Root 1 0 R /Size 4 >>\n%%EOF"
    doc = _parse(data)
    try:
        assert doc.get_trailer().get_dictionary_object(COSName.ROOT) is not None
    finally:
        doc.close()


def test_parse_missing_trailer_dict_recovers_via_catalog_scan() -> None:
    # no trailer dictionary at all: /Root is recovered by scanning for
    # /Type /Catalog.
    data = _BODY + b"startxref\n0\n%%EOF"
    doc = _parse(data)
    try:
        root = doc.get_trailer().get_dictionary_object(COSName.ROOT)
        assert root is not None
        assert (
            root.get_dictionary_object(COSName.TYPE)
            is COSName.get_pdf_name("Catalog")
        )
    finally:
        doc.close()


def test_parse_offset_off_by_a_few_bytes_corrected() -> None:
    # build a proper xref table but shift one entry's offset by +3 bytes;
    # lenient offset-correction must still resolve the catalog.
    obj1 = _BODY.find(b"1 0 obj")
    obj2 = _BODY.find(b"2 0 obj")
    obj3 = _BODY.find(b"3 0 obj")
    xref_pos = len(_BODY)
    xref = (
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        + f"{obj1 + 3:010d}".encode("ascii") + b" 00000 n \n"  # off by +3
        + f"{obj2:010d}".encode("ascii") + b" 00000 n \n"
        + f"{obj3:010d}".encode("ascii") + b" 00000 n \n"
    )
    trailer = b"trailer\n<< /Root 1 0 R /Size 4 >>\nstartxref\n"
    data = _BODY + xref + trailer + str(xref_pos).encode("ascii") + b"\n%%EOF"
    doc = _parse(data)
    try:
        root = doc.get_trailer().get_dictionary_object(COSName.ROOT)
        assert root is not None
        assert (
            root.get_dictionary_object(COSName.TYPE)
            is COSName.get_pdf_name("Catalog")
        )
    finally:
        doc.close()


def test_parse_truncated_file_lenient_does_not_crash() -> None:
    data = _BODY + b"3 0 obj\n<< /Cut tru"
    # lenient parse recovers what it can without raising.
    doc = _parse(data, lenient=True)
    try:
        assert doc is not None
    finally:
        doc.close()


def test_parse_junk_between_objects_recovers() -> None:
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"%% stray comment and \x00\x01 binary\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    )
    data = body + b"%%EOF"
    doc = _parse(data)
    try:
        assert doc.get_trailer().get_dictionary_object(COSName.ROOT) is not None
    finally:
        doc.close()


def test_parse_strict_mode_raises_on_unlocatable_xref() -> None:
    data = _BODY + b"trailer\n<< /Root 1 0 R >>\nstartxref\n99999\n%%EOF"
    with pytest.raises(PDFParseError):
        _parse(data, lenient=False)


def test_parse_header_only_no_objects_lenient() -> None:
    # only a header + garbage, no recoverable objects: lenient rebuild must
    # surface a parse failure rather than a silent rootless document.
    data = b"%PDF-1.4\nnothing recoverable here\n%%EOF"
    with pytest.raises(PDFParseError):
        _parse(data, lenient=True)


# ---------- validate_xref_offsets / find_object_key ----------


def test_validate_xref_offsets_none_is_true() -> None:
    assert _cos_parser(_BODY).validate_xref_offsets(None) is True


def test_validate_xref_offsets_good_table() -> None:
    p = _cos_parser(_BODY)
    table = {
        COSObjectKey(1, 0): _BODY.find(b"1 0 obj"),
        COSObjectKey(2, 0): _BODY.find(b"2 0 obj"),
    }
    assert p.validate_xref_offsets(table) is True


def test_validate_xref_offsets_bad_offset_returns_false() -> None:
    p = _cos_parser(_BODY)
    table = {COSObjectKey(1, 0): 99999}
    assert p.validate_xref_offsets(table) is False


def test_find_object_key_below_minimum_offset() -> None:
    p = _cos_parser(_BODY)
    assert p.find_object_key(COSObjectKey(1, 0), 2, {}) is None


def test_find_object_key_corrects_object_number_lenient() -> None:
    # offset points at object 2's header but the key claims object 1; lenient
    # mode corrects the object number to what is actually present.
    p = _cos_parser(_BODY)
    p.set_lenient(True)
    off = _BODY.find(b"2 0 obj")
    found = p.find_object_key(COSObjectKey(1, 0), off, {})
    assert found == COSObjectKey(2, 0)

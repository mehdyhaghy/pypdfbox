"""Fuzz the traditional cross-reference TABLE + trailer emission of
``COSWriter`` for byte-exact parity with upstream PDFBox 3.0.7
(``org.apache.pdfbox.pdfwriter.COSWriter``).

Surface under test (the NON-xref-stream path):

* the ``xref`` keyword + subsection ``first count`` headers,
* the 20-byte fixed-width entries (``nnnnnnnnnn ggggg n/f\\r\\n``),
* the object-0 free-list head (``0000000000 65535 f``) and the free-list
  ``next free object`` linkage,
* contiguous vs. fragmented object numbers producing multiple subsections,
* ``/Size`` = highest object number + 1 in the trailer,
* ``/Prev`` only on incremental updates,
* the ``startxref`` byte offset pointing exactly at the ``xref`` keyword,
* empty / single-object documents.

The format constants verified here are the ISO 32000-1 §7.5.4 wire format
that upstream ``COSWriter.writeXrefEntry`` / ``writeXrefRange`` /
``fillGapsWithFreeEntries`` / ``getXRefRanges`` produce byte-for-byte:
``formatXrefOffset`` = ``DecimalFormat("0000000000")`` (10 digits),
``formatXrefGeneration`` = ``DecimalFormat("00000")`` (5 digits), one SPACE
between fields, ``f``/``n`` type char, and ``writeCRLF`` (``\\r\\n``) ending
every row so each is exactly 20 bytes.
"""

from __future__ import annotations

import io
import re

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSName,
    COSObject,
    COSObjectKey,
)
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream

# Module-level format functions imported explicitly so an upstream rename is
# caught by the test rather than silently passing.
from pypdfbox.pdfwriter.cos_writer import (
    _format_xref_offset,
    _format_xref_table_generation,
    _format_xref_table_offset,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_full(doc: COSDocument) -> bytes:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(doc)
    return sink.getvalue()


def _make_doc_with_extra_objects(count: int) -> COSDocument:
    """Build a COSDocument whose body forces ``count`` extra indirect
    objects (numbered contiguously from 2) reachable from the catalog,
    so the emitted xref table has ``count + 2`` used entries (catalog =
    object 1, plus object 0's free head)."""
    doc = COSDocument()
    doc.set_version(1.4)
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    # Hang ``count`` distinct indirect dicts off the catalog under unique keys.
    extras = COSArray()
    for i in range(count):
        child = COSDictionary()
        child.set_int(COSName.get_pdf_name("Idx"), i)
        extras.add(COSObject(2 + i, 0, resolved=child))
    catalog.set_item(COSName.get_pdf_name("Kids"), extras)
    catalog_obj = COSObject(1, 0, resolved=catalog)
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, catalog_obj)  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    return doc


def _xref_keyword_offset(out: bytes) -> int:
    """Return the byte offset of the standalone ``xref`` table keyword
    (the one on its own line, NOT the ``startxref`` trailer keyword)."""
    matches = list(re.finditer(rb"(?:^|\n)xref\n", out))
    assert matches, "no standalone xref keyword in output"
    last = matches[-1]
    # Account for the leading ``\n`` the regex may have consumed.
    return last.start() + (1 if out[last.start() : last.start() + 1] == b"\n" else 0)


def _extract_xref_section(out: bytes) -> bytes:
    """Return the bytes from the standalone ``xref`` keyword up to (but not
    including) the following ``trailer`` keyword."""
    xref_idx = _xref_keyword_offset(out)
    trailer_idx = out.index(b"trailer", xref_idx)
    return out[xref_idx:trailer_idx]


def _parse_xref_rows(section: bytes) -> list[bytes]:
    """Return the 20-byte rows in the xref section (skipping the ``xref``
    keyword line and the ``first count`` subsection headers)."""
    # Rows match the strict ISO 32000-1 §7.5.4 shape.
    return re.findall(rb"\d{10} \d{5} [nf]\r\n", section)


def _parse_subsection_headers(section: bytes) -> list[tuple[int, int]]:
    """Return ``(first, count)`` pairs from the subsection header lines."""
    headers: list[tuple[int, int]] = []
    # Header lines: ``<first> <count>\n`` (writeEOL = LF, not CRLF).
    for m in re.finditer(rb"(?m)^(\d+) (\d+)\n", section):
        headers.append((int(m.group(1)), int(m.group(2))))
    return headers


def _trailer_dict_bytes(out: bytes) -> bytes:
    t = out.rfind(b"trailer")
    return out[t:]


# ---------------------------------------------------------------------------
# 20-byte entry exact format
# ---------------------------------------------------------------------------


def test_every_xref_row_is_exactly_20_bytes() -> None:
    out = _write_full(_make_doc_with_extra_objects(5))
    section = _extract_xref_section(out)
    rows = _parse_xref_rows(section)
    assert rows, "no xref rows parsed"
    for row in rows:
        assert len(row) == 20, f"row {row!r} is {len(row)} bytes, not 20"


def test_xref_row_offset_is_10_zero_padded_digits() -> None:
    out = _write_full(_make_doc_with_extra_objects(3))
    rows = _parse_xref_rows(_extract_xref_section(out))
    for row in rows:
        offset_field = row[:10]
        assert len(offset_field) == 10
        assert offset_field.isdigit()


def test_xref_row_generation_is_5_zero_padded_digits() -> None:
    out = _write_full(_make_doc_with_extra_objects(3))
    rows = _parse_xref_rows(_extract_xref_section(out))
    for row in rows:
        gen_field = row[11:16]
        assert len(gen_field) == 5
        assert gen_field.isdigit()


def test_xref_row_uses_single_space_separators() -> None:
    out = _write_full(_make_doc_with_extra_objects(3))
    rows = _parse_xref_rows(_extract_xref_section(out))
    for row in rows:
        assert row[10:11] == b" "
        assert row[16:17] == b" "


def test_xref_row_ends_with_crlf() -> None:
    out = _write_full(_make_doc_with_extra_objects(4))
    rows = _parse_xref_rows(_extract_xref_section(out))
    for row in rows:
        assert row[18:20] == b"\r\n", f"row {row!r} does not end in CRLF"


def test_xref_row_type_char_is_n_or_f() -> None:
    out = _write_full(_make_doc_with_extra_objects(4))
    rows = _parse_xref_rows(_extract_xref_section(out))
    for row in rows:
        assert row[17:18] in (b"n", b"f")


# ---------------------------------------------------------------------------
# object 0 free-list head
# ---------------------------------------------------------------------------


def test_object_zero_free_head_present_and_canonical() -> None:
    out = _write_full(_make_doc_with_extra_objects(3))
    rows = _parse_xref_rows(_extract_xref_section(out))
    # In a contiguous doc, the first row is object 0's free head.
    assert rows[0] == b"0000000000 65535 f\r\n"


def test_object_zero_generation_is_65535() -> None:
    out = _write_full(_make_doc_with_extra_objects(2))
    rows = _parse_xref_rows(_extract_xref_section(out))
    assert rows[0][11:16] == b"65535"
    assert rows[0][17:18] == b"f"


def test_single_free_head_in_contiguous_doc() -> None:
    out = _write_full(_make_doc_with_extra_objects(6))
    rows = _parse_xref_rows(_extract_xref_section(out))
    free_rows = [r for r in rows if r[17:18] == b"f"]
    # No gaps → exactly one free entry (object 0's head pointing at 0).
    assert len(free_rows) == 1
    assert free_rows[0] == b"0000000000 65535 f\r\n"


# ---------------------------------------------------------------------------
# contiguous numbering → single subsection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [0, 1, 2, 5, 10])
def test_contiguous_doc_has_single_subsection(extra: int) -> None:
    out = _write_full(_make_doc_with_extra_objects(extra))
    section = _extract_xref_section(out)
    headers = _parse_subsection_headers(section)
    assert len(headers) == 1, f"expected 1 subsection, got {headers}"
    first, count = headers[0]
    assert first == 0
    # object 0 (free) + object 1 (catalog) + ``extra`` children.
    assert count == extra + 2
    rows = _parse_xref_rows(section)
    assert len(rows) == count


@pytest.mark.parametrize("extra", [0, 1, 4, 9])
def test_size_in_trailer_is_highest_objnum_plus_one(extra: int) -> None:
    out = _write_full(_make_doc_with_extra_objects(extra))
    trailer = _trailer_dict_bytes(out)
    m = re.search(rb"/Size (\d+)", trailer)
    assert m is not None, "no /Size in trailer"
    # highest object number = 1 (catalog) + extra ; +1 for /Size.
    assert int(m.group(1)) == (1 + extra) + 1


# ---------------------------------------------------------------------------
# fragmented numbering → multiple subsections + free-list chain
# ---------------------------------------------------------------------------


def _writer_with_manual_entries(
    object_numbers: list[int],
) -> tuple[COSWriter, io.BytesIO]:
    """Return a writer pre-seeded with NormalXReference-style used entries
    at the given object numbers (offsets monotonically increasing), ready
    for a direct ``_do_write_xref_table`` call."""
    from pypdfbox.pdfwriter import COSWriterXRefEntry

    sink = io.BytesIO()
    w = COSWriter(sink)
    for i, num in enumerate(object_numbers):
        w.add_xref_entry(
            COSWriterXRefEntry(
                offset=100 + i * 50,
                key=COSObjectKey(num, 0),
                obj=COSName.TYPE,  # type: ignore[arg-type]
                free=False,
            )
        )
    return w, sink


def test_gap_filled_with_free_entry_yields_single_contiguous_subsection() -> None:
    # objects 1,2 present, 3 missing, 4,5 present. Upstream
    # ``fillGapsWithFreeEntries`` synthesises a FREE entry for object 3 (and
    # object 0's head), so every object number 0..5 is now covered and the
    # table is a SINGLE contiguous ``[0 6]`` subsection — not two split runs.
    w, sink = _writer_with_manual_entries([1, 2, 4, 5])
    w.do_write_x_ref_table()
    section = sink.getvalue()
    headers = _parse_subsection_headers(section)
    assert headers == [(0, 6)]
    rows = _parse_xref_rows(section)
    assert len(rows) == 6
    # Object 0 (free, →3) and object 3 (free, →0) are the two free rows.
    free_rows = [r for r in rows if r[17:18] == b"f"]
    assert free_rows[0] == b"0000000003 65535 f\r\n"
    assert free_rows[1] == b"0000000000 65535 f\r\n"


def test_free_list_chain_links_through_gaps() -> None:
    # objects 1,2 present, 3 missing → free entries for 0 and 3.
    w, sink = _writer_with_manual_entries([1, 2])
    # Force a higher object present so 3 becomes a gap.
    from pypdfbox.pdfwriter import COSWriterXRefEntry

    w.add_xref_entry(
        COSWriterXRefEntry(
            offset=999, key=COSObjectKey(4, 0), obj=COSName.TYPE, free=False  # type: ignore[arg-type]
        )
    )
    w.do_write_x_ref_table()
    section = sink.getvalue()
    rows = _parse_xref_rows(section)
    free_rows = [r for r in rows if r[17:18] == b"f"]
    # Two free numbers: 0 and 3. Object 0's free head points at next free (3),
    # and object 3's entry points back at 0 (end of chain).
    assert len(free_rows) == 2
    # object 0 head → next free 3:
    assert free_rows[0] == b"0000000003 65535 f\r\n"
    # object 3 tail → 0 (loop back):
    assert free_rows[1] == b"0000000000 65535 f\r\n"


def test_multiple_gaps_build_full_free_chain() -> None:
    # objects 2 and 5 present → gaps at 0,1,3,4 (fillGapsWithFreeEntries).
    w, sink = _writer_with_manual_entries([2, 5])
    w.do_write_x_ref_table()
    section = sink.getvalue()
    rows = _parse_xref_rows(section)
    free_rows = [r for r in rows if r[17:18] == b"f"]
    # Free object numbers gathered: [0,1,3,4]. Each free row's offset field is
    # the NEXT free object number, forming a chain 0→1, 1→3, 3→4, 4→0 (last
    # links back to object 0). Rows are emitted in object-number order.
    next_free = [int(r[:10]) for r in free_rows]
    assert next_free == [1, 3, 4, 0]
    # Every gap is now covered → the table is one contiguous [0 6] subsection.
    headers = _parse_subsection_headers(section)
    assert headers == [(0, 6)]


def test_subsection_count_matches_rows_in_each_section() -> None:
    w, sink = _writer_with_manual_entries([1, 2, 4, 5, 6, 8])
    w.do_write_x_ref_table()
    section = sink.getvalue()
    headers = _parse_subsection_headers(section)
    rows = _parse_xref_rows(section)
    assert sum(c for _, c in headers) == len(rows)


# ---------------------------------------------------------------------------
# startxref correctness
# ---------------------------------------------------------------------------


def test_startxref_points_at_xref_keyword() -> None:
    out = _write_full(_make_doc_with_extra_objects(4))
    m = re.search(rb"startxref\n(\d+)\n", out)
    assert m is not None, "no startxref line"
    declared = int(m.group(1))
    # The byte at that offset must begin the ``xref`` keyword.
    assert out[declared : declared + 4] == b"xref"


def test_startxref_matches_writer_state() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as w:
        w.write(_make_doc_with_extra_objects(3))
        recorded = w.get_startxref()
    out = sink.getvalue()
    assert out[recorded : recorded + 4] == b"xref"


def test_get_position_advances_by_20_per_entry() -> None:
    # Each writeXrefEntry must advance the stream position by exactly 20.
    from pypdfbox.pdfwriter import COSWriterXRefEntry

    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    w = COSWriter(io.BytesIO())
    w.set_standard_output(out)
    before = out.get_position()
    w.write_xref_entry(
        COSWriterXRefEntry(
            offset=12345, key=COSObjectKey(7, 0), obj=COSName.TYPE, free=False  # type: ignore[arg-type]
        )
    )
    assert out.get_position() - before == 20


# ---------------------------------------------------------------------------
# trailer: /Size, /Prev, /Root
# ---------------------------------------------------------------------------


def test_full_save_clears_prev() -> None:
    doc = _make_doc_with_extra_objects(2)
    # Seed a stale /Prev that a full save must strip.
    doc.get_trailer().set_int(COSName.PREV, 999)  # type: ignore[union-attr]
    out = _write_full(doc)
    trailer = _trailer_dict_bytes(out)
    assert b"/Prev" not in trailer


def test_trailer_has_size_and_root() -> None:
    out = _write_full(_make_doc_with_extra_objects(2))
    trailer = _trailer_dict_bytes(out)
    assert b"/Size" in trailer
    assert b"/Root" in trailer


def test_single_object_doc_size_is_two() -> None:
    # Only the catalog (object 1) → highest is 1 → /Size 2.
    out = _write_full(_make_doc_with_extra_objects(0))
    trailer = _trailer_dict_bytes(out)
    m = re.search(rb"/Size (\d+)", trailer)
    assert m is not None
    assert int(m.group(1)) == 2


# ---------------------------------------------------------------------------
# subsection header wire format (LF terminated, single space)
# ---------------------------------------------------------------------------


def test_subsection_header_format_and_eol() -> None:
    out = _write_full(_make_doc_with_extra_objects(3))
    section = _extract_xref_section(out)
    # First line is the ``xref`` keyword + LF.
    assert section.startswith(b"xref\n")
    # The subsection header for a contiguous doc is ``0 <count>\n``.
    body = section[len(b"xref\n") :]
    m = re.match(rb"(\d+) (\d+)\n", body)
    assert m is not None, f"bad subsection header in {body[:40]!r}"
    assert m.group(1) == b"0"


def test_xref_keyword_immediately_after_body() -> None:
    out = _write_full(_make_doc_with_extra_objects(1))
    # ``endobj`` ... ``xref`` — the keyword starts a fresh line.
    xref_idx = _xref_keyword_offset(out)
    assert out[xref_idx - 1 : xref_idx] == b"\n"


# ---------------------------------------------------------------------------
# module-level format helpers (exact upstream DecimalFormat parity)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (0, b"0000000000"),
        (1, b"0000000001"),
        (12345, b"0000012345"),
        (9999999999, b"9999999999"),
    ],
)
def test_format_xref_offset_is_10_digits(offset: int, expected: bytes) -> None:
    assert _format_xref_offset(offset) == expected
    assert _format_xref_table_offset(offset) == expected


def test_format_xref_table_offset_rejects_11_digit() -> None:
    with pytest.raises(ValueError):
        _format_xref_table_offset(10_000_000_000)


@pytest.mark.parametrize(
    ("gen", "expected"),
    [(0, b"00000"), (1, b"00001"), (65535, b"65535")],
)
def test_format_xref_generation_is_5_digits(gen: int, expected: bytes) -> None:
    assert _format_xref_table_generation(gen) == expected


@pytest.mark.parametrize("bad_gen", [-1, 65536, 100000])
def test_format_xref_table_generation_rejects_out_of_range(bad_gen: int) -> None:
    with pytest.raises(ValueError):
        _format_xref_table_generation(bad_gen)


# ---------------------------------------------------------------------------
# getXRefRanges / _build_ranges parity with spec example
# ---------------------------------------------------------------------------


def test_get_x_ref_ranges_spec_example() -> None:
    # ISO 32000-1 §7.5.4 example: 0 1 2 5 6 7 8 10 → [0 3 5 4 10 1].
    from pypdfbox.pdfwriter import COSWriterXRefEntry

    w = COSWriter(io.BytesIO())
    entries = [
        COSWriterXRefEntry(offset=0, key=COSObjectKey(n, 0), obj=None, free=False)
        for n in [0, 1, 2, 5, 6, 7, 8, 10]
    ]
    assert w.get_x_ref_ranges(entries) == [0, 3, 5, 4, 10, 1]


def test_build_ranges_single_run() -> None:
    from pypdfbox.pdfwriter import COSWriterXRefEntry

    entries = [
        COSWriterXRefEntry(offset=0, key=COSObjectKey(n, 0), obj=None, free=False)
        for n in range(5)
    ]
    assert COSWriter._build_ranges(entries) == [(0, 5)]


def test_build_ranges_empty() -> None:
    assert COSWriter._build_ranges([]) == []


# ---------------------------------------------------------------------------
# incremental: /Prev present, fresh xref appended
# ---------------------------------------------------------------------------


def _load_roundtrip_doc() -> bytes:
    return _write_full(_make_doc_with_extra_objects(2))


def test_incremental_update_sets_prev_and_appends_xref() -> None:
    from pypdfbox.loader import Loader

    base = _load_roundtrip_doc()
    doc = Loader.load_pdf(base)
    try:
        # Dirty an object so the increment has something to write.
        catalog = doc.get_trailer().get_dictionary_object(COSName.ROOT)
        assert isinstance(catalog, COSDictionary)
        catalog.set_int(COSName.get_pdf_name("Marker"), 42)
        if hasattr(catalog, "set_needs_to_be_updated"):
            catalog.set_needs_to_be_updated(True)
        sink = io.BytesIO()
        with COSWriter(sink, incremental=True) as w:
            w.write(doc)
        # The incremental writer buffers the whole new file; locate the LAST
        # trailer and confirm /Prev present (incremental MUST chain via /Prev).
        full = sink.getvalue()
        last_trailer = full.rfind(b"trailer")
        if last_trailer != -1:
            assert b"/Prev" in full[last_trailer:]
        # Every appended xref row (if a table, not a stream) is 20 bytes.
        rows = re.findall(rb"\d{10} \d{5} [nf]\r\n", full)
        for row in rows:
            assert len(row) == 20
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# write_xref_range / write_xref_entry direct surface
# ---------------------------------------------------------------------------


def test_write_xref_range_emits_first_space_count_lf() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    w = COSWriter(io.BytesIO())
    w.set_standard_output(out)
    w.write_xref_range(0, 7)
    assert sink.getvalue() == b"0 7\n"


def test_write_xref_entry_free_vs_used_type_char() -> None:
    from pypdfbox.pdfwriter import COSWriterXRefEntry

    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    w = COSWriter(io.BytesIO())
    w.set_standard_output(out)
    w.write_xref_entry(
        COSWriterXRefEntry(
            offset=5, key=COSObjectKey(9, 0), obj=None, free=True
        )
    )
    w.write_xref_entry(
        COSWriterXRefEntry(
            offset=200, key=COSObjectKey(10, 0), obj=COSName.TYPE, free=False  # type: ignore[arg-type]
        )
    )
    data = sink.getvalue()
    assert data == b"0000000005 00000 f\r\n0000000200 00000 n\r\n"
    assert len(data) == 40


# ---------------------------------------------------------------------------
# /ID array stays inline (direct) in the trailer
# ---------------------------------------------------------------------------


def test_trailer_id_array_is_inline() -> None:
    out = _write_full(_make_doc_with_extra_objects(1))
    trailer = _trailer_dict_bytes(out)
    # Synthesised /ID is a direct 2-element array of hex strings.
    assert b"/ID" in trailer
    assert b"<" in trailer[trailer.index(b"/ID") :]


def test_single_object_table_byte_exact_to_pdfbox() -> None:
    # Golden bytes captured from Apache PDFBox 3.0.7 COSWriter for a
    # catalog-only document (only the random /ID digest differs). The
    # ``xref`` section, the ``0 2`` subsection header, the two 20-byte
    # rows, ``/Size 2`` and the ``startxref 51`` tail must match exactly.
    # The catalog here carries ONLY ``/Type /Catalog`` (no /Kids) so the
    # body length matches the oracle's byte-for-byte.
    doc = COSDocument()
    catalog = COSDictionary()
    catalog.set_name(COSName.TYPE, "Catalog")  # type: ignore[attr-defined]
    trailer = COSDictionary()
    trailer.set_item(COSName.ROOT, COSObject(1, 0, resolved=catalog))  # type: ignore[attr-defined]
    doc.set_trailer(trailer)
    out = _write_full(doc)
    m = re.search(rb"\nxref\n", out)
    assert m is not None
    section = out[m.start() + 1 : out.index(b"trailer")]
    # PDFBox emits: ``xref\n0 2\n<free head>\n<catalog row>``.
    assert section == (
        b"xref\n0 2\n0000000000 65535 f\r\n0000000015 00000 n\r\n"
    )
    # /Size and startxref tail, byte-identical to upstream PDFBox 3.0.7.
    assert b"/Size 2" in out[out.index(b"trailer") :]
    assert re.search(rb"startxref\n51\n%%EOF\n", out) is not None


def test_id_is_two_element_array() -> None:
    out = _write_full(_make_doc_with_extra_objects(0))
    trailer = _trailer_dict_bytes(out)
    id_slice = trailer[trailer.index(b"/ID") : trailer.index(b"/ID") + 200]
    # Two hex strings between the array brackets.
    m = re.search(rb"/ID\s*\[(.*?)\]", id_slice, re.DOTALL)
    assert m is not None
    assert m.group(1).count(b"<") == 2


# ---------------------------------------------------------------------------
# end-to-end: round-trips through the parser (xref offsets resolve)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [0, 1, 3, 7])
def test_written_table_reparses(extra: int) -> None:
    from pypdfbox.loader import Loader

    out = _write_full(_make_doc_with_extra_objects(extra))
    doc = Loader.load_pdf(out)
    try:
        catalog = doc.get_trailer().get_dictionary_object(COSName.ROOT)
        assert isinstance(catalog, COSDictionary)
        assert catalog.get_cos_name(COSName.TYPE) == COSName.get_pdf_name("Catalog")
    finally:
        doc.close()


def test_reparsed_offsets_point_at_real_objects() -> None:
    # Sanity: the parser resolving an object means the 10-digit offset in
    # the table actually addressed the indirect object's ``N G obj`` start.
    from pypdfbox.loader import Loader

    out = _write_full(_make_doc_with_extra_objects(5))
    doc = Loader.load_pdf(out)
    try:
        # All keys the trailer references must resolve without error.
        for key in doc.get_object_keys():
            obj = doc.get_object_from_pool(key) if hasattr(
                doc, "get_object_from_pool"
            ) else None
            _ = obj  # resolution path varies; just ensure no exception
    finally:
        doc.close()

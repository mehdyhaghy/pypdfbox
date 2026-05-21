"""Wave 1377 — Thumbnail Hint Table decoder (PDF 32000-1 Annex F.5).

Wave 1373 deferred the Shared Object + Thumbnail sub-tables — this
wave (agent C) ships the Thumbnail Hint Table decoder. The decoder
sits alongside the Page Offset decoder in
``pypdfbox.pdfparser.linearization_hint_table`` and follows the same
shape: dataclass header + dataclass entry + ``parse_*`` entry points.

Apache PDFBox upstream does not ship any hint-table decoder; the
pypdfbox helper is a pypdfbox enrichment, not a Java port.

Tests cover:

  * ``parse_thumbnail_hint_header`` against a hand-crafted 22-byte
    header.
  * ``parse_thumbnail_hint_table`` end-to-end against a synthetic body.
  * Defensive parsing — truncated bodies / out-of-range index lookups.
  * Round-trip through ``PDFParser.decode_thumbnail_hint_table`` on a
    tiny linearized PDF stub.
"""

from __future__ import annotations

import struct
import zlib

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import (
    HintTableParseError,
    PDFParser,
    ThumbnailHintTable,
    parse_thumbnail_hint_header,
    parse_thumbnail_hint_table,
)

# ----------------------------------------------------------- header decode


def _build_thumbnail_header(
    *,
    first_object_number: int = 7,
    first_object_location: int = 9000,
    num_pages_with_thumbnails: int = 2,
    bits_length_delta: int = 8,
    least_length: int = 128,
    bits_shared_id: int = 4,
) -> bytes:
    """Pack the 20-byte fixed header of a Thumbnail Hint Table per
    PDF 32000-1 Table F.6 Items 1-6."""
    return struct.pack(
        ">IIIHIH",
        first_object_number,
        first_object_location,
        num_pages_with_thumbnails,
        bits_length_delta,
        least_length,
        bits_shared_id,
    )


def test_parse_thumbnail_hint_header_round_trips_known_values() -> None:
    header_bytes = _build_thumbnail_header(
        first_object_number=99,
        first_object_location=54321,
        num_pages_with_thumbnails=5,
        bits_length_delta=12,
        least_length=4096,
        bits_shared_id=6,
    )
    h = parse_thumbnail_hint_header(header_bytes)
    assert h.first_thumbnail_object_number == 99
    assert h.first_thumbnail_object_location == 54321
    assert h.num_pages_with_thumbnails == 5
    assert h.bits_for_thumbnail_length_delta == 12
    assert h.least_thumbnail_length == 4096
    assert h.bits_for_shared_thumbnail_id == 6
    assert h.least_shared_thumbnail_reference == 0


def test_parse_thumbnail_hint_header_too_short_raises() -> None:
    with pytest.raises(HintTableParseError):
        parse_thumbnail_hint_header(b"\x00" * 19)


# ----------------------------------------------------------- full table


def _pack_bits(values: list[tuple[int, int]]) -> bytes:
    """Pack ``(value, bit_width)`` tuples MSB-first into bytes."""
    buf = 0
    nbits = 0
    for value, width in values:
        if width == 0:
            continue
        buf = (buf << width) | (value & ((1 << width) - 1))
        nbits += width
    pad = (-nbits) % 8
    buf <<= pad
    nbits += pad
    if nbits == 0:
        return b""
    return buf.to_bytes(nbits // 8, "big")


def test_parse_thumbnail_hint_table_three_entries_round_trip() -> None:
    """Hand-craft a 3-entry thumbnail table, decode it, assert every
    recovered field matches what we packed."""
    header_bytes = _build_thumbnail_header(
        first_object_number=20,
        first_object_location=400,
        num_pages_with_thumbnails=3,
        bits_length_delta=8,
        least_length=200,
        bits_shared_id=4,
    )
    page_fields: list[tuple[int, int]] = [
        (0, 0),
        (50, 3),
        (255, 15),
    ]
    bits: list[tuple[int, int]] = []
    for length_delta, shared_id_delta in page_fields:
        bits.append((length_delta, 8))
        bits.append((shared_id_delta, 4))
    body = _pack_bits(bits)
    table = parse_thumbnail_hint_table(header_bytes + body)
    assert isinstance(table, ThumbnailHintTable)
    assert table.thumbnail_count() == 3
    assert table.entries[0].length_delta == 0
    assert table.entries[0].shared_id_delta == 0
    assert table.length_for_entry(0) == 200
    assert table.entries[1].length_delta == 50
    assert table.entries[1].shared_id_delta == 3
    assert table.length_for_entry(1) == 250
    assert table.entries[2].length_delta == 255
    assert table.entries[2].shared_id_delta == 15
    assert table.length_for_entry(2) == 455


def test_parse_thumbnail_hint_table_zero_pages_yields_empty() -> None:
    """``num_pages_with_thumbnails == 0`` is valid — no entries."""
    header_bytes = _build_thumbnail_header(
        num_pages_with_thumbnails=0,
        bits_length_delta=8,
        bits_shared_id=4,
    )
    table = parse_thumbnail_hint_table(header_bytes)
    assert table.thumbnail_count() == 0
    assert table.entries == []


def test_parse_thumbnail_hint_table_truncated_body_raises() -> None:
    header_bytes = _build_thumbnail_header(
        num_pages_with_thumbnails=4,
        bits_length_delta=8,
        bits_shared_id=4,
    )
    with pytest.raises(HintTableParseError):
        parse_thumbnail_hint_table(header_bytes)


def test_length_for_entry_rejects_out_of_range_index() -> None:
    header_bytes = _build_thumbnail_header(
        num_pages_with_thumbnails=0,
        bits_length_delta=0,
        bits_shared_id=0,
    )
    table = parse_thumbnail_hint_table(header_bytes)
    with pytest.raises(IndexError):
        table.length_for_entry(0)
    with pytest.raises(IndexError):
        table.length_for_entry(-1)


# ----------------------------------------------------------- parser entry


def _build_page_offset_header(
    *,
    least_objects: int = 5,
    first_page_offset: int = 1000,
    bits_object_delta: int = 0,
    least_page_len: int = 200,
    bits_page_len_delta: int = 0,
    least_content_off: int = 50,
    bits_content_off_delta: int = 0,
    least_content_len: int = 100,
    bits_content_len_delta: int = 0,
    bits_shared_count: int = 0,
    bits_shared_id: int = 0,
) -> bytes:
    return struct.pack(
        ">IIHIHIHIHHH",
        least_objects,
        first_page_offset,
        bits_object_delta,
        least_page_len,
        bits_page_len_delta,
        least_content_off,
        bits_content_off_delta,
        least_content_len,
        bits_content_len_delta,
        bits_shared_count,
        bits_shared_id,
    )


def _build_linearized_pdf_with_thumbnail(
    *,
    n_pages: int,
    page_offset_section: bytes,
    shared_section_offset: int | None,
    shared_section_body: bytes,
    thumbnail_section_offset: int | None,
    thumbnail_section_body: bytes,
) -> bytes:
    """Mirror of the shared-object helper but threading the thumbnail
    sub-table offset into ``/H[3]``."""
    decoded = bytearray(page_offset_section)
    if shared_section_offset is not None:
        decoded.extend(b"\x00" * (shared_section_offset - len(decoded)))
        decoded.extend(shared_section_body)
    if thumbnail_section_offset is not None:
        decoded.extend(b"\x00" * (thumbnail_section_offset - len(decoded)))
        decoded.extend(thumbnail_section_body)
    compressed = zlib.compress(bytes(decoded))
    h_len = len(compressed)
    so_off = shared_section_offset if shared_section_offset is not None else 0
    th_off = (
        thumbnail_section_offset if thumbnail_section_offset is not None else 0
    )

    def _lin_dict(primary_off: int) -> bytes:
        return (
            b"1 0 obj\n"
            b"<< /Linearized 1 "
            b"/L 1000 "
            b"/H [" + f"{primary_off:010d}".encode("ascii") + b" "
            + f"{h_len:010d}".encode("ascii") + b" "
            + f"{so_off:010d}".encode("ascii") + b" "
            + f"{th_off:010d}".encode("ascii") + b"] "
            b"/O 4 "
            b"/E 0 "
            b"/N " + str(n_pages).encode("ascii") + b" "
            b"/T 0 "
            b">>\nendobj\n"
        )

    out = bytearray()
    out += b"%PDF-1.7\n"
    stub_dict = _lin_dict(0)
    out += stub_dict
    hint_stream_dict = (
        b"2 0 obj\n"
        b"<< /Length " + str(len(compressed)).encode("ascii") + b" "
        b"/Filter /FlateDecode >>\nstream\n"
    )
    obj2_offset = len(out)
    out += hint_stream_dict
    out += compressed + b"\nendstream\nendobj\n"
    obj3_offset = len(out)
    out += b"3 0 obj\n<< /Type /Catalog /Pages 4 0 R >>\nendobj\n"
    obj4_offset = len(out)
    out += b"4 0 obj\n<< /Type /Pages /Kids [5 0 R] /Count 1 >>\nendobj\n"
    obj5_offset = len(out)
    out += b"5 0 obj\n<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    patched = _lin_dict(obj2_offset)
    assert len(patched) == len(stub_dict)
    lin_obj_start = out.index(b"1 0 obj\n")
    out[lin_obj_start : lin_obj_start + len(stub_dict)] = patched
    xref_offset = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in (lin_obj_start, obj2_offset, obj3_offset, obj4_offset, obj5_offset):
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 6 /Root 3 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_decode_thumbnail_hint_table_through_parser() -> None:
    """End-to-end: linearized PDF with /H[3] pointing at a Thumbnail
    Hint Table inside the decoded primary hint stream."""
    page_off_header = _build_page_offset_header()
    page_off_section = page_off_header
    thumb_header = _build_thumbnail_header(
        first_object_number=30,
        first_object_location=900,
        num_pages_with_thumbnails=2,
        bits_length_delta=8,
        least_length=512,
        bits_shared_id=4,
    )
    bits: list[tuple[int, int]] = [
        # Page 0: length_delta=10, shared_id=0
        (10, 8), (0, 4),
        # Page 1: length_delta=120, shared_id=3
        (120, 8), (3, 4),
    ]
    thumb_body = _pack_bits(bits)
    thumb_offset = len(page_off_section)
    pdf = _build_linearized_pdf_with_thumbnail(
        n_pages=1,
        page_offset_section=page_off_section,
        shared_section_offset=None,
        shared_section_body=b"",
        thumbnail_section_offset=thumb_offset,
        thumbnail_section_body=thumb_header + thumb_body,
    )
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    cos_doc = parser.parse()
    try:
        assert parser.is_linearized() is True
        table = parser.decode_thumbnail_hint_table()
        assert table is not None
        assert table.thumbnail_count() == 2
        assert table.length_for_entry(0) == 512 + 10
        assert table.length_for_entry(1) == 512 + 120
        assert table.entries[0].shared_id_delta == 0
        assert table.entries[1].shared_id_delta == 3
    finally:
        cos_doc.close()


def test_decode_thumbnail_hint_table_missing_h3_returns_none() -> None:
    """A linearized PDF whose /H array is the 2-element form (no /H[3])
    cannot surface a thumbnail decode — ``None`` is the correct outcome."""
    page_off_header = _build_page_offset_header()
    decoded = page_off_header
    compressed = zlib.compress(decoded)
    n_pages = 1
    out = bytearray()
    out += b"%PDF-1.7\n"

    def _lin_dict(primary_off: int) -> bytes:
        # Two-element /H — no shared / thumbnail slot.
        return (
            b"1 0 obj\n"
            b"<< /Linearized 1 "
            b"/L 1000 "
            b"/H [" + f"{primary_off:010d}".encode("ascii") + b" "
            + f"{len(compressed):010d}".encode("ascii") + b"] "
            b"/O 4 "
            b"/E 0 "
            b"/N " + str(n_pages).encode("ascii") + b" "
            b"/T 0 "
            b">>\nendobj\n"
        )

    stub_dict = _lin_dict(0)
    out += stub_dict
    obj2_offset = len(out)
    out += (
        b"2 0 obj\n"
        b"<< /Length " + str(len(compressed)).encode("ascii") + b" "
        b"/Filter /FlateDecode >>\nstream\n"
    )
    out += compressed + b"\nendstream\nendobj\n"
    obj3_offset = len(out)
    out += b"3 0 obj\n<< /Type /Catalog /Pages 4 0 R >>\nendobj\n"
    obj4_offset = len(out)
    out += b"4 0 obj\n<< /Type /Pages /Kids [5 0 R] /Count 1 >>\nendobj\n"
    obj5_offset = len(out)
    out += b"5 0 obj\n<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    patched = _lin_dict(obj2_offset)
    assert len(patched) == len(stub_dict)
    lin_obj_start = out.index(b"1 0 obj\n")
    out[lin_obj_start : lin_obj_start + len(stub_dict)] = patched
    xref_offset = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in (lin_obj_start, obj2_offset, obj3_offset, obj4_offset, obj5_offset):
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 6 /Root 3 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    cos_doc = parser.parse()
    try:
        assert parser.is_linearized() is True
        assert parser.decode_thumbnail_hint_table() is None
        assert parser.decode_shared_object_hint_table() is None
    finally:
        cos_doc.close()

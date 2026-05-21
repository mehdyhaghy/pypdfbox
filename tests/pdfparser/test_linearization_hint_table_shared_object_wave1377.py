"""Wave 1377 — Shared Object Hint Table decoder (PDF 32000-1 Annex F.4).

Wave 1373 deferred the Shared Object + Thumbnail sub-tables — this
wave (agent C) ships the Shared Object Hint Table decoder. The decoder
sits alongside the Page Offset decoder in
``pypdfbox.pdfparser.linearization_hint_table`` and follows the same
shape: dataclass header + dataclass entry + ``parse_*`` entry points.

Apache PDFBox upstream does not ship any hint-table decoder; the
pypdfbox helper is a pypdfbox enrichment, not a Java port.

Tests cover:

  * ``parse_shared_object_hint_header`` against a hand-crafted 24-byte
    header.
  * ``parse_shared_object_hint_table`` end-to-end against a synthetic
    body with mixed signature-flag entries.
  * Defensive parsing — truncated bodies / out-of-range index lookups.
  * Round-trip through ``PDFParser.decode_shared_object_hint_table`` on
    a tiny linearized PDF stub.
"""

from __future__ import annotations

import struct
import zlib

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import (
    HintTableParseError,
    PDFParser,
    SharedObjectHintTable,
    parse_shared_object_hint_header,
    parse_shared_object_hint_table,
)
from pypdfbox.pdfparser.linearization_hint_table import _BitReader

# ----------------------------------------------------------- header decode


def _build_shared_object_header(
    *,
    first_object_number: int = 100,
    first_object_location: int = 5000,
    num_first_page: int = 2,
    num_total: int = 4,
    bits_group_count: int = 2,
    least_length: int = 50,
    bits_length_delta: int = 6,
) -> bytes:
    """Pack the 24-byte fixed header of a Shared Object Hint Table per
    PDF 32000-1 Table F.4 Items 1-7."""
    return struct.pack(
        ">IIIIHIH",
        first_object_number,
        first_object_location,
        num_first_page,
        num_total,
        bits_group_count,
        least_length,
        bits_length_delta,
    )


def test_parse_shared_object_hint_header_round_trips_known_values() -> None:
    header_bytes = _build_shared_object_header(
        first_object_number=42,
        first_object_location=12345,
        num_first_page=3,
        num_total=7,
        bits_group_count=4,
        least_length=64,
        bits_length_delta=10,
    )
    h = parse_shared_object_hint_header(header_bytes)
    assert h.first_shared_object_number == 42
    assert h.first_shared_object_location == 12345
    assert h.num_shared_objects_first_page == 3
    assert h.num_shared_objects_total == 7
    assert h.bits_for_group_object_count == 4
    assert h.least_shared_object_length == 64
    assert h.bits_for_shared_object_length_delta == 10


def test_parse_shared_object_hint_header_too_short_raises() -> None:
    with pytest.raises(HintTableParseError):
        parse_shared_object_hint_header(b"\x00" * 23)


# ----------------------------------------------------------- full table


def _pack_bits(values: list[tuple[int, int]]) -> bytes:
    """Pack a list of ``(value, bit_width)`` tuples MSB-first into a
    minimal bytes blob. Inverse of ``_BitReader``."""
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


def test_bit_reader_round_trips_md5_block() -> None:
    """A 128-bit MD5 packed via _pack_bits round-trips through
    _BitReader byte-by-byte — guards the shared-object sig path."""
    md5 = bytes(range(16))
    bits: list[tuple[int, int]] = []
    for byte in md5:
        bits.append((byte, 8))
    blob = _pack_bits(bits)
    reader = _BitReader(blob)
    recovered = bytes(reader.read(8) for _ in range(16))
    assert recovered == md5


def test_parse_shared_object_hint_table_mixed_signatures() -> None:
    """Hand-craft a 3-entry shared-object table mixing signed and
    unsigned entries; assert every field round-trips."""
    header_bytes = _build_shared_object_header(
        first_object_number=10,
        first_object_location=200,
        num_first_page=1,
        num_total=3,
        bits_group_count=3,
        least_length=80,
        bits_length_delta=8,
    )
    md5_a = bytes(range(16))
    md5_b = bytes(range(16, 32))
    # Three entries: (length_delta=10, signed=True, md5=md5_a, group=2),
    # (length_delta=0, signed=False, md5=N/A, group=0),
    # (length_delta=255, signed=True, md5=md5_b, group=7).
    bits: list[tuple[int, int]] = []
    # Entry 1
    bits.append((10, 8))
    bits.append((1, 1))
    for byte in md5_a:
        bits.append((byte, 8))
    bits.append((2, 3))
    # Entry 2
    bits.append((0, 8))
    bits.append((0, 1))
    bits.append((0, 3))
    # Entry 3
    bits.append((255, 8))
    bits.append((1, 1))
    for byte in md5_b:
        bits.append((byte, 8))
    bits.append((7, 3))
    body = _pack_bits(bits)
    table = parse_shared_object_hint_table(header_bytes + body)
    assert isinstance(table, SharedObjectHintTable)
    assert table.shared_object_count() == 3
    assert table.entries[0].length_delta == 10
    assert table.entries[0].signature_present is True
    assert table.entries[0].signature_md5 == md5_a
    assert table.entries[0].group_object_count == 2
    assert table.length_for_entry(0) == 80 + 10
    assert table.entries[1].length_delta == 0
    assert table.entries[1].signature_present is False
    assert table.entries[1].signature_md5 == b""
    assert table.entries[1].group_object_count == 0
    assert table.length_for_entry(1) == 80
    assert table.entries[2].length_delta == 255
    assert table.entries[2].signature_present is True
    assert table.entries[2].signature_md5 == md5_b
    assert table.entries[2].group_object_count == 7
    assert table.length_for_entry(2) == 80 + 255


def test_parse_shared_object_hint_table_zero_total_yields_empty() -> None:
    """``num_shared_objects_total == 0`` is valid — no per-entry block."""
    header_bytes = _build_shared_object_header(
        num_total=0,
        bits_length_delta=8,
        bits_group_count=4,
    )
    table = parse_shared_object_hint_table(header_bytes)
    assert table.shared_object_count() == 0
    assert table.entries == []


def test_parse_shared_object_hint_table_truncated_body_raises() -> None:
    """A header is present but the per-entry block is missing — must
    raise ``HintTableParseError``."""
    header_bytes = _build_shared_object_header(
        num_total=4,
        bits_length_delta=8,
        bits_group_count=4,
    )
    with pytest.raises(HintTableParseError):
        parse_shared_object_hint_table(header_bytes)


def test_length_for_entry_rejects_out_of_range_index() -> None:
    header_bytes = _build_shared_object_header(
        num_total=0,
        bits_length_delta=0,
        bits_group_count=0,
    )
    table = parse_shared_object_hint_table(header_bytes)
    with pytest.raises(IndexError):
        table.length_for_entry(0)
    with pytest.raises(IndexError):
        table.length_for_entry(-1)


# ----------------------------------------------------------- parser entry


def _build_page_offset_header(
    *,
    least_objects: int = 5,
    first_page_offset: int = 1000,
    bits_object_delta: int = 4,
    least_page_len: int = 200,
    bits_page_len_delta: int = 8,
    least_content_off: int = 50,
    bits_content_off_delta: int = 8,
    least_content_len: int = 100,
    bits_content_len_delta: int = 8,
    bits_shared_count: int = 4,
    bits_shared_id: int = 8,
) -> bytes:
    """Page Offset Hint Table 32-byte header (Items 1-11)."""
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


def _build_linearized_pdf_with_subtables(
    *,
    n_pages: int,
    page_offset_section: bytes,
    shared_section_offset: int | None,
    shared_section_body: bytes,
    thumbnail_section_offset: int | None,
    thumbnail_section_body: bytes,
) -> bytes:
    """Assemble a tiny linearized PDF whose primary hint stream packs
    the Page Offset Hint Table, optionally followed by Shared Object
    and Thumbnail sub-tables. Sub-table offsets are surfaced via the
    pypdfbox-specific ``/H[2]`` and ``/H[3]`` slots."""
    decoded = bytearray(page_offset_section)
    if shared_section_offset is not None:
        assert shared_section_offset >= len(decoded), (
            "shared section must come after page-offset table"
        )
        # Pad to shared offset
        decoded.extend(b"\x00" * (shared_section_offset - len(decoded)))
        decoded.extend(shared_section_body)
    if thumbnail_section_offset is not None:
        assert thumbnail_section_offset >= len(decoded)
        decoded.extend(b"\x00" * (thumbnail_section_offset - len(decoded)))
        decoded.extend(thumbnail_section_body)
    compressed = zlib.compress(bytes(decoded))
    # /H array: [primary_off primary_len shared_subtable_off thumb_subtable_off]
    h_off_placeholder = 0
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
    stub_dict = _lin_dict(h_off_placeholder)
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
    assert len(patched) == len(stub_dict), (len(patched), len(stub_dict))
    lin_obj_start = out.index(b"1 0 obj\n")
    out[lin_obj_start : lin_obj_start + len(stub_dict)] = patched
    xref_offset = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in (lin_obj_start, obj2_offset, obj3_offset, obj4_offset, obj5_offset):
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 6 /Root 3 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_decode_shared_object_hint_table_through_parser() -> None:
    """End-to-end: linearized PDF with /H array carrying a Shared
    Object sub-table offset. ``PDFParser.decode_shared_object_hint_table``
    must decode the entries."""
    page_off_header = _build_page_offset_header(
        bits_object_delta=0,
        bits_page_len_delta=0,
        bits_content_off_delta=0,
        bits_content_len_delta=0,
        bits_shared_count=0,
    )
    page_off_section = page_off_header  # zero-bit page block is empty
    shared_header = _build_shared_object_header(
        first_object_number=20,
        first_object_location=500,
        num_first_page=1,
        num_total=2,
        bits_group_count=0,
        least_length=64,
        bits_length_delta=8,
    )
    bits: list[tuple[int, int]] = [
        # Entry 1: length_delta=5, no signature
        (5, 8), (0, 1),
        # Entry 2: length_delta=100, no signature
        (100, 8), (0, 1),
    ]
    shared_body = _pack_bits(bits)
    shared_offset = len(page_off_section)
    pdf = _build_linearized_pdf_with_subtables(
        n_pages=1,
        page_offset_section=page_off_section,
        shared_section_offset=shared_offset,
        shared_section_body=shared_header + shared_body,
        thumbnail_section_offset=None,
        thumbnail_section_body=b"",
    )
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    cos_doc = parser.parse()
    try:
        assert parser.is_linearized() is True
        table = parser.decode_shared_object_hint_table()
        assert table is not None
        assert table.shared_object_count() == 2
        assert table.length_for_entry(0) == 64 + 5
        assert table.length_for_entry(1) == 64 + 100
        assert table.entries[0].signature_present is False
        assert table.entries[1].signature_present is False
    finally:
        cos_doc.close()


def test_decode_shared_object_hint_table_on_non_linearized_pdf() -> None:
    """Non-linearized PDFs surface ``None`` from the decoder helper."""
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Count 0 >>\nendobj\n"
    )
    obj1_off = pdf.find(b"1 0 obj")
    obj2_off = pdf.find(b"2 0 obj")
    xref_off = len(pdf)
    pdf += b"xref\n0 3\n0000000000 65535 f \n"
    pdf += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    pdf += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    pdf += b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
    pdf += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    cos_doc = parser.parse()
    try:
        assert parser.is_linearized() is False
        assert parser.decode_shared_object_hint_table() is None
    finally:
        cos_doc.close()

"""Wave 1373 — Page Offset Hint Table decoder (PDF 32000-1 Annex F.3).

CHANGES.md:721 deferred the hint-table body decode in wave 41 as
"page-offset / shared-object / thumbnail tables inside the hint stream
are deferred to a deeper port". This wave ships the Page Offset Hint
Table decoder (most useful for web-streaming consumers) at
``pypdfbox.pdfparser.linearization_hint_table``. The Shared Object and
Thumbnail sub-tables remain deferred — see CHANGES.md for the scoping
note.

Apache PDFBox upstream does not ship any hint-table decoder; the
pypdfbox helper is a pypdfbox enrichment, not a Java port.

Tests cover:

  * the bit-packed ``_BitReader`` helper across MSB-first and byte-
    boundary cases
  * ``parse_page_offset_hint_header`` against a hand-crafted 32-byte
    header
  * ``parse_page_offset_hint_table`` end-to-end against a 3-page
    synthetic hint stream
  * defensive parsing — truncated bodies / unrealistic page counts
"""

from __future__ import annotations

import struct
import zlib

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import (
    HintTableParseError,
    PageOffsetHintTable,
    PDFParser,
    parse_page_offset_hint_header,
    parse_page_offset_hint_table,
)
from pypdfbox.pdfparser.linearization_hint_table import _BitReader

# ----------------------------------------------------------- _BitReader


def test_bit_reader_msb_first_within_byte() -> None:
    """A single byte split into 3 + 5 bits returns MSB-first."""
    r = _BitReader(b"\xA5")  # 0b10100101
    assert r.read(3) == 0b101
    assert r.read(5) == 0b00101


def test_bit_reader_crosses_byte_boundary() -> None:
    """12-bit read crossing two bytes returns the MSB-first packing."""
    # 0xAB = 0b10101011, 0xCD = 0b11001101
    # First 12 bits = 0b101010111100 = 0xABC
    r = _BitReader(b"\xAB\xCD")
    assert r.read(12) == 0xABC
    # Remaining 4 bits = 0b1101 = 0xD
    assert r.read(4) == 0xD


def test_bit_reader_zero_width_returns_zero() -> None:
    """Zero-width reads are how the spec encodes 'all rows share value'."""
    r = _BitReader(b"\xFF")
    assert r.read(0) == 0
    # Cursor must not have advanced.
    assert r.read(8) == 0xFF


def test_bit_reader_overrun_raises() -> None:
    r = _BitReader(b"\x01")
    with pytest.raises(HintTableParseError):
        r.read(9)


def test_bit_reader_align_to_byte() -> None:
    """``align_to_byte`` skips to the next byte boundary."""
    r = _BitReader(b"\xF0\x0F")
    assert r.read(4) == 0xF
    r.align_to_byte()
    assert r.read(8) == 0x0F


# ----------------------------------------------------------- header decode


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
    bits_fraction_numerator: int = 0,
    fraction_denominator: int = 0,
) -> bytes:
    """Pack the 36-byte fixed header of a Page Offset Hint Table per
    PDF 32000-1 Table F.3 Items 1-13. The trailing items 12 + 13 are
    part of the fixed header — wave 1452 fixed the decoder that
    previously stopped at byte 32 and bled the next 4 bytes into the
    per-page bit stream."""
    return struct.pack(
        ">IIHIHIHIHHHHH",
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
        bits_fraction_numerator,
        fraction_denominator,
    )


def test_parse_page_offset_hint_header_round_trips_known_values() -> None:
    header_bytes = _build_page_offset_header(
        least_objects=7,
        first_page_offset=9876,
        bits_object_delta=3,
        least_page_len=512,
        bits_page_len_delta=10,
        least_content_off=64,
        bits_content_off_delta=6,
        least_content_len=128,
        bits_content_len_delta=12,
        bits_shared_count=5,
        bits_shared_id=9,
    )
    h = parse_page_offset_hint_header(header_bytes)
    assert h.least_objects_per_page == 7
    assert h.first_page_object_offset == 9876
    assert h.bits_for_object_count_delta == 3
    assert h.least_page_length == 512
    assert h.bits_for_page_length_delta == 10
    assert h.least_content_stream_offset == 64
    assert h.bits_for_content_stream_offset_delta == 6
    assert h.least_content_stream_length == 128
    assert h.bits_for_content_stream_length_delta == 12
    assert h.bits_for_shared_object_count == 5
    assert h.bits_for_shared_object_id == 9
    assert h.bits_for_fraction_numerator == 0
    assert h.fraction_denominator == 0


def test_parse_page_offset_hint_header_too_short_raises() -> None:
    with pytest.raises(HintTableParseError):
        parse_page_offset_hint_header(b"\x00" * 30)


# ----------------------------------------------------------- full table


def _pack_bits(values: list[tuple[int, int]]) -> bytes:
    """Pack a list of ``(value, bit_width)`` tuples MSB-first into a
    minimal bytes blob. The packing inverse of ``_BitReader``."""
    buf = 0
    nbits = 0
    for value, width in values:
        if width == 0:
            continue
        buf = (buf << width) | (value & ((1 << width) - 1))
        nbits += width
    # Pad to byte alignment with zeros on the LSB side.
    pad = (-nbits) % 8
    buf <<= pad
    nbits += pad
    return buf.to_bytes(nbits // 8, "big")


class _BitWriter:
    """Append bits and align to byte boundaries — the encoder twin of
    the column-major reader used by the production decoder. Calls to
    :meth:`align_to_byte` zero-pad to the next byte boundary, matching
    qpdf's ``skipToNextByte`` between successive column reads."""

    def __init__(self) -> None:
        self._buf = 0
        self._nbits = 0

    def write(self, value: int, width: int) -> None:
        if width == 0:
            return
        self._buf = (self._buf << width) | (value & ((1 << width) - 1))
        self._nbits += width

    def align_to_byte(self) -> None:
        pad = (-self._nbits) % 8
        if pad:
            self._buf <<= pad
            self._nbits += pad

    def to_bytes(self) -> bytes:
        self.align_to_byte()
        return self._buf.to_bytes(self._nbits // 8, "big")


def _pack_page_offset_body(
    *,
    bits_object_delta: int,
    bits_page_len_delta: int,
    bits_content_off_delta: int,
    bits_content_len_delta: int,
    bits_shared_count: int,
    bits_shared_id: int,
    bits_shared_numerator: int,
    page_fields: list[tuple[int, int, int, int, int]],
) -> bytes:
    """Encode the per-page block in **column-major** order matching the
    decoder. Each column ends with a byte alignment, the same way the
    reference qpdf reader emits ``skipToNextByte`` between successive
    ``load_vector_int`` calls."""
    w = _BitWriter()
    # Column 1 — obj_count_delta across all pages.
    for ocd, _, _, _, _ in page_fields:
        w.write(ocd, bits_object_delta)
    w.align_to_byte()
    # Column 2 — page_length_delta across all pages.
    for _, pld, _, _, _ in page_fields:
        w.write(pld, bits_page_len_delta)
    w.align_to_byte()
    # Column 3 — nshared_objects across all pages.
    for _, _, _, _, sc in page_fields:
        w.write(sc, bits_shared_count)
    w.align_to_byte()
    # Column 4 — shared_identifiers (one per shared ref per page) —
    # empty when all shared counts are zero; we leave it empty for
    # this fixture which uses non-zero shared counts but with zero
    # identifier bit width is impractical, so for this test we write
    # `nshared * bits_shared_id` zero bits per page.
    for _, _, _, _, sc in page_fields:
        for _ in range(sc):
            w.write(0, bits_shared_id)
    w.align_to_byte()
    # Column 5 — shared_numerators (one per shared ref per page).
    for _, _, _, _, sc in page_fields:
        for _ in range(sc):
            w.write(0, bits_shared_numerator)
    w.align_to_byte()
    # Column 6 — content_offset_delta across all pages.
    for _, _, cod, _, _ in page_fields:
        w.write(cod, bits_content_off_delta)
    w.align_to_byte()
    # Column 7 — content_length_delta across all pages.
    for _, _, _, cld, _ in page_fields:
        w.write(cld, bits_content_len_delta)
    w.align_to_byte()
    return w.to_bytes()


def test_parse_page_offset_hint_table_three_pages_round_trip() -> None:
    """Hand-craft a 3-page hint table column-major encoded per the spec,
    decode it, assert every recovered field matches what we packed."""
    header_bytes = _build_page_offset_header(
        least_objects=3,
        first_page_offset=1024,
        bits_object_delta=4,
        least_page_len=500,
        bits_page_len_delta=8,
        least_content_off=10,
        bits_content_off_delta=4,
        least_content_len=200,
        bits_content_len_delta=6,
        bits_shared_count=2,
        bits_shared_id=4,
    )
    # Three pages, five fields per row: obj-count delta, page-len delta,
    # content-off delta, content-len delta, shared-count. Encoded
    # column-major per the qpdf-reference layout.
    page_fields: list[tuple[int, int, int, int, int]] = [
        (0, 0, 0, 0, 0),
        (5, 60, 12, 40, 1),
        (10, 120, 14, 50, 2),
    ]
    body = _pack_page_offset_body(
        bits_object_delta=4,
        bits_page_len_delta=8,
        bits_content_off_delta=4,
        bits_content_len_delta=6,
        bits_shared_count=2,
        bits_shared_id=4,
        bits_shared_numerator=0,
        page_fields=page_fields,
    )
    table = parse_page_offset_hint_table(header_bytes + body, page_count=3)
    assert isinstance(table, PageOffsetHintTable)
    assert table.page_count() == 3
    # Page 0 — all deltas zero ⇒ each helper returns the "least" value.
    assert table.object_count_for_page(0) == 3
    assert table.page_length_for_page(0) == 500
    assert table.content_stream_offset_for_page(0) == 10
    assert table.content_stream_length_for_page(0) == 200
    assert table.pages[0].shared_object_count == 0
    # Page 1 — apply each delta.
    assert table.object_count_for_page(1) == 3 + 5
    assert table.page_length_for_page(1) == 500 + 60
    assert table.content_stream_offset_for_page(1) == 10 + 12
    assert table.content_stream_length_for_page(1) == 200 + 40
    assert table.pages[1].shared_object_count == 1
    # Page 2 — larger deltas.
    assert table.object_count_for_page(2) == 3 + 10
    assert table.page_length_for_page(2) == 500 + 120
    assert table.content_stream_offset_for_page(2) == 10 + 14
    assert table.content_stream_length_for_page(2) == 200 + 50
    assert table.pages[2].shared_object_count == 2


def test_parse_page_offset_hint_table_truncated_body_raises() -> None:
    """A header is present but the per-page block is missing — must
    raise ``HintTableParseError``."""
    header_bytes = _build_page_offset_header(
        bits_object_delta=8,
        bits_page_len_delta=8,
        bits_content_off_delta=8,
        bits_content_len_delta=8,
        bits_shared_count=8,
    )
    # Page count 4 means 4 rows × (8+8+8+8+8) = 160 bits = 20 bytes,
    # but supply zero post-header bytes.
    with pytest.raises(HintTableParseError):
        parse_page_offset_hint_table(header_bytes, page_count=4)


def test_parse_page_offset_hint_table_zero_page_count_raises() -> None:
    header_bytes = _build_page_offset_header()
    with pytest.raises(HintTableParseError):
        parse_page_offset_hint_table(header_bytes, page_count=0)


def test_page_offset_helpers_reject_out_of_range_index() -> None:
    header_bytes = _build_page_offset_header(
        bits_object_delta=0,
        bits_page_len_delta=0,
        bits_content_off_delta=0,
        bits_content_len_delta=0,
        bits_shared_count=0,
    )
    table = parse_page_offset_hint_table(header_bytes, page_count=1)
    with pytest.raises(IndexError):
        table.object_count_for_page(1)
    with pytest.raises(IndexError):
        table.page_length_for_page(-1)
    with pytest.raises(IndexError):
        table.content_stream_offset_for_page(5)
    with pytest.raises(IndexError):
        table.content_stream_length_for_page(99)


# ----------------------------------------------------------- parser entry


def _build_linearized_pdf_with_flate_hint(
    *,
    n_pages: int,
    page_offset_header_bytes: bytes,
    page_offset_body_bytes: bytes,
) -> bytes:
    """Assemble a tiny linearized PDF whose hint stream object is a
    ``/FlateDecode`` stream wrapping a concrete Page Offset Hint Table.
    Mirrors the structure of ``tests/pdfparser/test_linearized.py``'s
    helper but with a real hint payload."""
    decoded = page_offset_header_bytes + page_offset_body_bytes
    compressed = zlib.compress(decoded)
    out = bytearray()
    out += b"%PDF-1.7\n"
    # Stub linearization dict — patched once we know the hint stream
    # body offset.
    stub_dict = (
        b"1 0 obj\n"
        b"<< /Linearized 1 "
        b"/L 1000 "
        b"/H [0000000000 0000000000] "
        b"/O 4 "
        b"/E 0 "
        b"/N " + str(n_pages).encode("ascii") + b" "
        b"/T 0 "
        b">>\nendobj\n"
    )
    out += stub_dict
    # Hint stream object 2 — /FlateDecode body.
    hint_stream_dict = (
        b"2 0 obj\n"
        b"<< /Length " + str(len(compressed)).encode("ascii") + b" "
        b"/Filter /FlateDecode >>\nstream\n"
    )
    obj2_offset = len(out)
    # ``obj2_offset`` is the byte position of "2 0 obj" — that's what
    # the linearization dict's ``/H[0]`` must point at.
    out += hint_stream_dict
    out += compressed + b"\nendstream\nendobj\n"
    obj3_offset = len(out)
    out += b"3 0 obj\n<< /Type /Catalog /Pages 4 0 R >>\nendobj\n"
    obj4_offset = len(out)
    out += b"4 0 obj\n<< /Type /Pages /Kids [5 0 R] /Count 1 >>\nendobj\n"
    obj5_offset = len(out)
    out += b"5 0 obj\n<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    # Patch the linearization dict — /H[0] = object 2's byte offset.
    patched = (
        b"1 0 obj\n"
        b"<< /Linearized 1 "
        b"/L 1000 "
        b"/H [" + f"{obj2_offset:010d}".encode("ascii") + b" "
        + f"{len(compressed):010d}".encode("ascii") + b"] "
        b"/O 4 "
        b"/E 0 "
        b"/N " + str(n_pages).encode("ascii") + b" "
        b"/T 0 "
        b">>\nendobj\n"
    )
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


def test_decode_page_offset_hint_table_through_parser() -> None:
    """End-to-end: build a 2-page linearized PDF whose primary hint
    stream is a ``/FlateDecode`` body containing a real Page Offset
    Hint Table. ``PDFParser.decode_page_offset_hint_table()`` must
    return a table with both rows recovered."""
    header = _build_page_offset_header(
        least_objects=4,
        first_page_offset=200,
        bits_object_delta=4,
        least_page_len=300,
        bits_page_len_delta=8,
        least_content_off=20,
        bits_content_off_delta=4,
        least_content_len=150,
        bits_content_len_delta=6,
        bits_shared_count=0,
        bits_shared_id=0,
    )
    page_fields: list[tuple[int, int, int, int, int]] = [
        # Page 0 — zero deltas.
        (0, 0, 0, 0, 0),
        # Page 1 — assorted deltas.
        (3, 25, 5, 20, 0),
    ]
    body = _pack_page_offset_body(
        bits_object_delta=4,
        bits_page_len_delta=8,
        bits_content_off_delta=4,
        bits_content_len_delta=6,
        bits_shared_count=0,
        bits_shared_id=0,
        bits_shared_numerator=0,
        page_fields=page_fields,
    )
    pdf = _build_linearized_pdf_with_flate_hint(
        n_pages=2,
        page_offset_header_bytes=header,
        page_offset_body_bytes=body,
    )
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    cos_doc = parser.parse()
    try:
        assert parser.is_linearized() is True
        table = parser.decode_page_offset_hint_table()
        assert table is not None
        assert table.page_count() == 2
        assert table.object_count_for_page(0) == 4
        assert table.object_count_for_page(1) == 4 + 3
        assert table.page_length_for_page(1) == 300 + 25
        assert table.content_stream_offset_for_page(1) == 20 + 5
        assert table.content_stream_length_for_page(1) == 150 + 20
    finally:
        cos_doc.close()


def test_decode_page_offset_hint_table_on_non_linearized_pdf() -> None:
    """Non-linearized PDFs surface ``None`` from the decoder helper —
    there's no /H to follow."""
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
        assert parser.decode_page_offset_hint_table() is None
    finally:
        cos_doc.close()

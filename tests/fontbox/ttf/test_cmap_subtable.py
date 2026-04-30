from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _CmapStub:
    """Minimal stand-in for ``CmapTable`` — only exposes ``get_offset()``."""

    def __init__(self, offset: int = 0) -> None:
        self._offset = offset

    def get_offset(self) -> int:
        return self._offset


# ---------------------------------------------------------------------------
# Class-level basics
# ---------------------------------------------------------------------------


def test_cmap_subtable_is_a_cmap_lookup() -> None:
    sub = CmapSubtable()
    assert isinstance(sub, CmapLookup)


def test_cmap_subtable_default_state() -> None:
    sub = CmapSubtable()
    assert sub.get_platform_id() == 0
    assert sub.get_platform_encoding_id() == 0
    # No data loaded yet -> all lookups miss.
    assert sub.get_glyph_id(0x41) == 0
    assert sub.get_char_codes(1) is None


def test_cmap_subtable_setters() -> None:
    sub = CmapSubtable()
    sub.set_platform_id(3)
    sub.set_platform_encoding_id(10)
    assert sub.get_platform_id() == 3
    assert sub.get_platform_encoding_id() == 10


def test_pdfbox_camelcase_metadata_aliases() -> None:
    sub = CmapSubtable()
    sub.setPlatformId(3)
    sub.setPlatformEncodingId(10)

    assert sub.getPlatformId() == 3
    assert sub.getPlatformEncodingId() == 10


def test_cmap_subtable_repr() -> None:
    sub = CmapSubtable()
    sub.set_platform_id(3)
    sub.set_platform_encoding_id(1)
    assert repr(sub) == "{3 1}"


def test_cmap_subtable_init_data_reads_three_fields() -> None:
    # platformId (uint16), platformEncodingId (uint16), subtableOffset (uint32)
    blob = struct.pack(">HHI", 3, 1, 0x1234)
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_data(data)
    assert sub.get_platform_id() == 3
    assert sub.get_platform_encoding_id() == 1
    # _sub_table_offset is private; just round-trip through init_subtable would
    # use it. Here we just sanity check via attribute.
    assert sub._sub_table_offset == 0x1234  # noqa: SLF001


# ---------------------------------------------------------------------------
# Format 0 (byte encoding table): 256-byte glyph map
# ---------------------------------------------------------------------------


def _build_format0(glyph_mapping: bytes) -> bytes:
    assert len(glyph_mapping) == 256
    # format(uint16=0), length(uint16, ignored), version(uint16, ignored), then 256 bytes.
    return struct.pack(">HHH", 0, 262, 0) + glyph_mapping


def test_format_0_identity_mapping_round_trips() -> None:
    # Identity: char code i -> glyph id i (for i in 0..255).
    glyph_mapping = bytes(range(256))
    blob = _build_format0(glyph_mapping)
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(offset=0), num_glyphs=256, data=data)
    for code in (0, 1, 0x41, 0x7F, 0xFF):
        assert sub.get_glyph_id(code) == code
        assert sub.get_char_codes(code) == [code]


def test_format_0_custom_mapping() -> None:
    mapping = bytearray(range(256))
    # Swap: code 0x41 -> glyph 0x10, code 0x42 -> glyph 0x20
    mapping[0x41] = 0x10
    mapping[0x42] = 0x20
    blob = _build_format0(bytes(mapping))
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=256, data=data)
    assert sub.get_glyph_id(0x41) == 0x10
    assert sub.get_glyph_id(0x42) == 0x20
    # Reverse lookup: glyph 0x10 was assigned at i=0x41 (overwriting the
    # earlier mapping at i=0x10 -- the loop walks i=0..255 in order, so
    # glyph_id_to_character_code[0x10] ends up = 0x41).
    assert sub.get_char_codes(0x10) == [0x41]
    assert sub.get_char_codes(0x20) == [0x42]


# ---------------------------------------------------------------------------
# Format 4 (segmented mapping for BMP)
# ---------------------------------------------------------------------------


def _build_format4_two_segments() -> bytes:
    """One real segment ['A'..'D' -> gid 1..4] plus the mandatory 0xFFFF terminator."""
    # Segment 1: start='A'(0x41), end='D'(0x44), idDelta = -0x40 (so 0x41 + (-0x40) = 1).
    # idDelta is stored as uint16; -0x40 mod 65536 = 0xFFC0.
    # Segment 2 (terminator): start=end=0xFFFF, delta=1, range_offset=0.
    seg_count = 2
    seg_count_x2 = seg_count * 2
    end_count = [0x0044, 0xFFFF]
    start_count = [0x0041, 0xFFFF]
    id_delta = [0xFFC0, 1]
    id_range_offset = [0, 0]

    payload = struct.pack(">H", seg_count_x2)
    payload += struct.pack(">HHH", 0, 0, 0)  # searchRange/entrySelector/rangeShift (ignored)
    payload += struct.pack(f">{seg_count}H", *end_count)
    payload += struct.pack(">H", 0)  # reservedPad
    payload += struct.pack(f">{seg_count}H", *start_count)
    payload += struct.pack(f">{seg_count}H", *id_delta)
    payload += struct.pack(f">{seg_count}H", *id_range_offset)

    # format(uint16=4), length(uint16, ignored), version(uint16, ignored)
    return struct.pack(">HHH", 4, 0, 0) + payload


def test_format_4_segmented_mapping_round_trip() -> None:
    blob = _build_format4_two_segments()
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)

    # Forward lookups
    assert sub.get_glyph_id(0x41) == 1
    assert sub.get_glyph_id(0x42) == 2
    assert sub.get_glyph_id(0x43) == 3
    assert sub.get_glyph_id(0x44) == 4
    # Outside any segment -> 0
    assert sub.get_glyph_id(0x40) == 0
    assert sub.get_glyph_id(0x45) == 0

    # Reverse lookups
    assert sub.get_char_codes(1) == [0x41]
    assert sub.get_char_codes(4) == [0x44]
    assert sub.get_char_codes(99) is None


# ---------------------------------------------------------------------------
# Format 6 (trimmed table mapping)
# ---------------------------------------------------------------------------


def _build_format6(first_code: int, glyph_id_array: list[int]) -> bytes:
    # format(uint16=6), length(uint16, ignored), version(uint16, ignored),
    # firstCode(uint16), entryCount(uint16), glyphIdArray (uint16 * entryCount)
    payload = struct.pack(">HH", first_code, len(glyph_id_array))
    payload += struct.pack(f">{len(glyph_id_array)}H", *glyph_id_array)
    return struct.pack(">HHH", 6, 0, 0) + payload


def test_format_6_trimmed_table_round_trip() -> None:
    # Codes 0x30..0x33 -> glyph ids 10, 11, 12, 13
    blob = _build_format6(0x30, [10, 11, 12, 13])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)

    assert sub.get_glyph_id(0x30) == 10
    assert sub.get_glyph_id(0x31) == 11
    assert sub.get_glyph_id(0x32) == 12
    assert sub.get_glyph_id(0x33) == 13
    assert sub.get_glyph_id(0x34) == 0  # outside range

    assert sub.get_char_codes(10) == [0x30]
    assert sub.get_char_codes(13) == [0x33]
    assert sub.get_char_codes(99) is None


def test_pdfbox_camelcase_lookup_aliases() -> None:
    blob = _build_format6(0x30, [10, 11, 12])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)

    assert sub.getGlyphId(0x30) == 10
    assert sub.getGlyphId(0x31) == 11
    assert sub.getCharCode(10) == 0x30
    assert sub.getCharCodes(12) == [0x32]
    assert sub.getCharCodes(99) is None
    assert sub.hasUVS() is False
    assert sub.getGlyphIdUVS(0x30, 0xFE0F) == 0


def test_format_6_zero_entries_does_not_crash() -> None:
    blob = _build_format6(0x30, [])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=0, data=data)
    # Empty table -> nothing maps.
    assert sub.get_glyph_id(0x30) == 0


# ---------------------------------------------------------------------------
# Format 12 (segmented coverage UCS-4)
# ---------------------------------------------------------------------------


def _build_format12(groups: list[tuple[int, int, int]]) -> bytes:
    # format(uint16=12), reserved(uint16), length(uint32, ignored),
    # language/version(uint32, ignored), nGroups(uint32), then triples of uint32.
    payload = struct.pack(">I", len(groups))
    for first, end, start_glyph in groups:
        payload += struct.pack(">III", first, end, start_glyph)
    return struct.pack(">HHII", 12, 0, 0, 0) + payload


def test_format_12_single_group_bmp() -> None:
    # Codes 0x41..0x43 -> glyph ids 1..3
    blob = _build_format12([(0x41, 0x43, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)

    assert sub.get_glyph_id(0x41) == 1
    assert sub.get_glyph_id(0x42) == 2
    assert sub.get_glyph_id(0x43) == 3
    assert sub.get_glyph_id(0x44) == 0

    assert sub.get_char_codes(1) == [0x41]
    assert sub.get_char_codes(3) == [0x43]


def test_format_12_supplementary_plane() -> None:
    # Supplementary plane: 0x1F600..0x1F602 -> glyph ids 5..7
    blob = _build_format12([(0x1F600, 0x1F602, 5)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)

    assert sub.get_glyph_id(0x1F600) == 5
    assert sub.get_glyph_id(0x1F601) == 6
    assert sub.get_glyph_id(0x1F602) == 7
    assert sub.get_char_codes(7) == [0x1F602]


def test_format_12_invalid_first_code_in_surrogate_range_raises() -> None:
    # 0xD800 is a surrogate -> not a valid Unicode scalar.
    blob = _build_format12([(0xD800, 0xD801, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    with pytest.raises(OSError):
        sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)


def test_format_12_first_code_above_max_raises() -> None:
    blob = _build_format12([(0x110000, 0x110001, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    with pytest.raises(OSError):
        sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)


def test_format_12_zero_num_glyphs_logs_and_returns(caplog: pytest.LogCaptureFixture) -> None:
    blob = _build_format12([(0x41, 0x42, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=0, data=data)
    # No mappings established.
    assert sub.get_glyph_id(0x41) == 0


# ---------------------------------------------------------------------------
# Multiple character codes mapping to the same glyph (reverse-lookup multi-map)
# ---------------------------------------------------------------------------


def test_format_6_multiple_char_codes_to_same_glyph_returns_sorted_list() -> None:
    # Codes 0x40..0x42 -> glyph 7 (all three)
    blob = _build_format6(0x40, [7, 7, 7])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)
    # Reverse lookup must include all three character codes, sorted.
    assert sub.get_char_codes(7) == [0x40, 0x41, 0x42]


# ---------------------------------------------------------------------------
# Unsupported / deferred formats
# ---------------------------------------------------------------------------


def test_unknown_format_raises_oserror() -> None:
    # Format 99 is not a real OpenType cmap format.
    # Format >=8 -> reads reserved(uint16), length(uint32), version(uint32) before raising.
    blob = struct.pack(">HHII", 99, 0, 0, 0)
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    with pytest.raises(OSError):
        sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)


# ---------------------------------------------------------------------------
# get_char_codes edge cases
# ---------------------------------------------------------------------------


def test_get_char_codes_negative_gid_returns_none() -> None:
    blob = _build_format6(0x30, [10])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)
    assert sub.get_char_codes(-1) is None


def test_get_char_codes_out_of_range_gid_returns_none() -> None:
    blob = _build_format6(0x30, [10])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)
    # max gid populated is 10; 9999 is beyond the lookup table.
    assert sub.get_char_codes(9999) is None

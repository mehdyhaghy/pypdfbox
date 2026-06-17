"""Fuzz / parity tests for the OpenType ``cmap`` subtable format parsers.

Hammers the format readers in ``pypdfbox.fontbox.ttf.cmap_subtable`` against
synthetically-assembled subtable bytes, checking the bit-arithmetic that is the
historically bug-prone part of each format:

* Format 0  - the 256-byte glyph-index array (code -> gid) and its reverse map.
* Format 4  - segment mapping, BOTH the ``idRangeOffset == 0`` arithmetic
  (``gid = (code + idDelta) & 0xFFFF``) and the ``idRangeOffset != 0`` case
  that resolves the gid through the glyphIndexArray pointer arithmetic
  (``segmentRangeOffset + (code - start) * 2``), plus the mandatory 0xFFFF
  terminating segment and the ``glyphIndex == 0 -> not mapped`` rule.
* Format 6  - trimmed table (``firstCode .. firstCode + entryCount - 1``).
* Format 10 - trimmed 32-bit array.
* Format 12 - segmented coverage groups
  (``startCharCode .. endCharCode -> startGlyphID + offset``), inclusive end.

These mirror upstream ``org.apache.fontbox.ttf.CmapSubtable`` (PDFBox 3.0.7)
``processSubtype{0,4,6,10,12}`` and the reverse-lookup helpers
``getCharCode`` / ``getCharCodes`` (ported as ``get_char_code`` /
``get_char_codes``).
"""
from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _CmapStub:
    """Minimal stand-in for ``CmapTable`` exposing only ``get_offset()``."""

    def __init__(self, offset: int = 0) -> None:
        self._offset = offset

    def get_offset(self) -> int:
        return self._offset


def _run(blob: bytes, num_glyphs: int, offset: int = 0) -> CmapSubtable:
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(offset), num_glyphs=num_glyphs, data=data)
    return sub


# ---------------------------------------------------------------------------
# Format 0 (byte encoding, 256-glyph array)
# ---------------------------------------------------------------------------


def _build_format0(glyph_mapping: bytes) -> bytes:
    assert len(glyph_mapping) == 256
    # format(uint16=0), length(uint16, ignored), version(uint16, ignored)
    return struct.pack(">HHH", 0, 262, 0) + glyph_mapping


def test_format_0_identity_mapping() -> None:
    mapping = bytes(range(256))
    sub = _run(_build_format0(mapping), num_glyphs=256)
    for code in (0, 1, 0x41, 0x80, 0xFE, 0xFF):
        assert sub.get_glyph_id(code) == code
    # reverse
    assert sub.get_char_code(0x41) == 0x41
    assert sub.get_char_codes(0x41) == [0x41]


def test_format_0_permuted_mapping() -> None:
    # code i -> gid (255 - i)
    mapping = bytes(255 - i for i in range(256))
    sub = _run(_build_format0(mapping), num_glyphs=256)
    assert sub.get_glyph_id(0) == 255
    assert sub.get_glyph_id(255) == 0
    assert sub.get_glyph_id(0x40) == 255 - 0x40
    assert sub.get_char_codes(255) == [0]
    assert sub.get_char_codes(0) == [255]


def test_format_0_high_byte_masking() -> None:
    # All bytes 0xFF -> gid 255; reverse slot keeps the LAST code (255) but the
    # array build keeps first-wins so multiple codes funnel into the multimap.
    mapping = b"\xff" * 256
    sub = _run(_build_format0(mapping), num_glyphs=256)
    assert sub.get_glyph_id(0) == 0xFF
    assert sub.get_glyph_id(0x12) == 0xFF
    # gid 0 is never mapped by any code -> reverse slot stays at sentinel -1.
    assert sub.get_char_code(0) == -1
    # reverse for gid 0xFF: format-0 writes glyph_id_to_character_code directly
    # (no multimap), last code wins -> 255.
    assert sub.get_char_code(0xFF) == 255


def test_format_0_uncovered_high_codes_map_to_zero_gid() -> None:
    # Only code 0x10 -> gid 5, everything else -> gid 0.
    mapping = bytearray(256)
    mapping[0x10] = 5
    sub = _run(_build_format0(bytes(mapping)), num_glyphs=256)
    assert sub.get_glyph_id(0x10) == 5
    # All other codes map to gid 0 (their array byte is 0).
    assert sub.get_glyph_id(0x11) == 0
    assert sub.get_glyph_id(0xAB) == 0


# ---------------------------------------------------------------------------
# Format 4 (segment mapping) - idRangeOffset == 0 branch
# ---------------------------------------------------------------------------


def _build_format4(
    segments: list[tuple[int, int, int, int]],
    glyph_index_array: list[int] | None = None,
) -> bytes:
    """Assemble a format-4 subtable.

    ``segments`` is a list of (startCode, endCode, idDelta, idRangeOffset).
    The mandatory 0xFFFF terminator must be included by the caller. Any
    ``glyph_index_array`` is appended verbatim after the idRangeOffset array
    (this is the region idRangeOffset != 0 segments index into).
    """
    seg_count = len(segments)
    seg_count_x2 = seg_count * 2
    end_count = [s[1] for s in segments]
    start_count = [s[0] for s in segments]
    id_delta = [s[2] & 0xFFFF for s in segments]
    id_range_offset = [s[3] for s in segments]

    payload = struct.pack(">H", seg_count_x2)
    payload += struct.pack(">HHH", 0, 0, 0)  # searchRange/entrySelector/rangeShift
    payload += struct.pack(f">{seg_count}H", *end_count)
    payload += struct.pack(">H", 0)  # reservedPad
    payload += struct.pack(f">{seg_count}H", *start_count)
    payload += struct.pack(f">{seg_count}H", *id_delta)
    payload += struct.pack(f">{seg_count}H", *id_range_offset)
    if glyph_index_array:
        payload += struct.pack(f">{len(glyph_index_array)}H", *glyph_index_array)

    # format(uint16=4), length(uint16, ignored), version(uint16, ignored)
    return struct.pack(">HHH", 4, 0, 0) + payload


def test_format_4_id_range_offset_zero_basic() -> None:
    # 'A'..'D' -> gid 1..4 via idDelta = -0x40 (0xFFC0 mod 65536), terminator.
    segs = [(0x41, 0x44, -0x40, 0), (0xFFFF, 0xFFFF, 1, 0)]
    sub = _run(_build_format4(segs), num_glyphs=10)
    assert sub.get_glyph_id(0x41) == 1
    assert sub.get_glyph_id(0x44) == 4
    assert sub.get_glyph_id(0x40) == 0
    assert sub.get_glyph_id(0x45) == 0
    assert sub.get_char_codes(1) == [0x41]
    assert sub.get_char_codes(4) == [0x44]


def test_format_4_id_delta_wraps_mod_65536() -> None:
    # idDelta chosen so (code + delta) overflows 16 bits -> must wrap mod 65536.
    # code 0x0002, delta = 0xFFFF -> (2 + 0xFFFF) & 0xFFFF = 1.
    segs = [(0x0001, 0x0003, 0xFFFF, 0), (0xFFFF, 0xFFFF, 1, 0)]
    sub = _run(_build_format4(segs), num_glyphs=10)
    assert sub.get_glyph_id(0x0001) == 0x0000
    assert sub.get_glyph_id(0x0002) == 0x0001
    assert sub.get_glyph_id(0x0003) == 0x0002


def test_format_4_terminator_segment_not_mapped() -> None:
    segs = [(0x10, 0x12, 0, 0), (0xFFFF, 0xFFFF, 1, 0)]
    sub = _run(_build_format4(segs), num_glyphs=10)
    # 0xFFFF terminator must NOT produce a mapping for code 0xFFFF.
    assert sub.get_glyph_id(0xFFFF) == 0
    # Real segment still maps (idDelta 0 -> gid == code).
    assert sub.get_glyph_id(0x10) == 0x10
    assert sub.get_glyph_id(0x12) == 0x12


def test_format_4_multiple_real_segments() -> None:
    segs = [
        (0x20, 0x22, -0x1F, 0),  # 0x20->1, 0x21->2, 0x22->3
        (0x30, 0x31, -0x2B, 0),  # 0x30->5, 0x31->6
        (0xFFFF, 0xFFFF, 1, 0),
    ]
    sub = _run(_build_format4(segs), num_glyphs=20)
    assert sub.get_glyph_id(0x20) == 1
    assert sub.get_glyph_id(0x22) == 3
    assert sub.get_glyph_id(0x30) == 5
    assert sub.get_glyph_id(0x31) == 6
    # gap between segments
    assert sub.get_glyph_id(0x23) == 0
    assert sub.get_glyph_id(0x2F) == 0


# ---------------------------------------------------------------------------
# Format 4 - idRangeOffset != 0 branch (glyphIndexArray pointer arithmetic)
# ---------------------------------------------------------------------------


def test_format_4_id_range_offset_nonzero_basic() -> None:
    # One real segment with idRangeOffset != 0. There are 2 segments; the
    # glyphIndexArray sits right after the idRangeOffset array.
    #
    # idRangeOffsetPosition points at idRangeOffset[0]. For segment 0 (i=0):
    #   segmentRangeOffset = idRangeOffsetPos + 0 + rangeOffset
    # rangeOffset is in bytes. The glyphIndexArray begins at
    #   idRangeOffsetPos + segCount*2  (just past the 2-entry rangeOffset array).
    # So to make segment 0 point at glyphIndexArray[0], rangeOffset must be:
    #   (segCount - i) * 2 = (2 - 0) * 2 = 4.
    glyph_index_array = [7, 8, 9]  # for codes 0x41, 0x42, 0x43
    segs = [(0x41, 0x43, 0, 4), (0xFFFF, 0xFFFF, 1, 0)]
    sub = _run(_build_format4(segs, glyph_index_array), num_glyphs=20)
    assert sub.get_glyph_id(0x41) == 7
    assert sub.get_glyph_id(0x42) == 8
    assert sub.get_glyph_id(0x43) == 9
    assert sub.get_glyph_id(0x40) == 0
    assert sub.get_glyph_id(0x44) == 0
    assert sub.get_char_codes(8) == [0x42]


def test_format_4_id_range_offset_nonzero_applies_id_delta() -> None:
    # glyphIndex != 0 -> final gid = (glyphIndex + idDelta) & 0xFFFF.
    glyph_index_array = [10, 20, 30]
    segs = [(0x41, 0x43, 5, 4), (0xFFFF, 0xFFFF, 1, 0)]
    sub = _run(_build_format4(segs, glyph_index_array), num_glyphs=64)
    assert sub.get_glyph_id(0x41) == 15
    assert sub.get_glyph_id(0x42) == 25
    assert sub.get_glyph_id(0x43) == 35


def test_format_4_id_range_offset_nonzero_zero_glyph_index_unmapped() -> None:
    # A glyphIndexArray entry of 0 means "missing glyph" -> not stored at all,
    # even though idDelta is non-zero. Upstream skips the put entirely.
    glyph_index_array = [11, 0, 13]
    segs = [(0x41, 0x43, 5, 4), (0xFFFF, 0xFFFF, 1, 0)]
    sub = _run(_build_format4(segs, glyph_index_array), num_glyphs=64)
    assert sub.get_glyph_id(0x41) == 16
    assert sub.get_glyph_id(0x42) == 0  # glyphIndex 0 -> unmapped, delta NOT applied
    assert sub.get_glyph_id(0x43) == 18


def test_format_4_id_range_offset_nonzero_offset_into_later_slot() -> None:
    # rangeOffset can point past glyphIndexArray[0]: use rangeOffset = 4 + 2*1
    # to start at glyphIndexArray[1].
    glyph_index_array = [99, 41, 42, 43]
    segs = [(0x41, 0x43, 0, 6), (0xFFFF, 0xFFFF, 1, 0)]
    sub = _run(_build_format4(segs, glyph_index_array), num_glyphs=64)
    assert sub.get_glyph_id(0x41) == 41
    assert sub.get_glyph_id(0x42) == 42
    assert sub.get_glyph_id(0x43) == 43


def test_format_4_mixed_offset_and_delta_segments() -> None:
    # Segment 0 uses idDelta, segment 1 uses idRangeOffset.
    # seg_count = 3 (incl terminator). glyphIndexArray after rangeOffset array.
    # For segment i=1 to reach glyphIndexArray[0]:
    #   rangeOffset = (segCount - i) * 2 = (3 - 1) * 2 = 4.
    glyph_index_array = [50, 51]
    segs = [
        (0x10, 0x11, 0, 0),       # delta segment: 0x10->0x10, 0x11->0x11
        (0x20, 0x21, 0, 4),       # offset segment -> glyphIndexArray[0..1]
        (0xFFFF, 0xFFFF, 1, 0),
    ]
    sub = _run(_build_format4(segs, glyph_index_array), num_glyphs=64)
    assert sub.get_glyph_id(0x10) == 0x10
    assert sub.get_glyph_id(0x11) == 0x11
    assert sub.get_glyph_id(0x20) == 50
    assert sub.get_glyph_id(0x21) == 51


def test_format_4_nonzero_cmap_offset_arithmetic_holds() -> None:
    # Same content but the whole subtable lives at a non-zero cmap offset; the
    # idRangeOffset pointer arithmetic uses absolute stream positions, so it
    # must still resolve correctly.
    glyph_index_array = [7, 8, 9]
    segs = [(0x41, 0x43, 0, 4), (0xFFFF, 0xFFFF, 1, 0)]
    pad = b"\x00" * 13
    blob = pad + _build_format4(segs, glyph_index_array)
    sub = _run(blob, num_glyphs=20, offset=len(pad))
    assert sub.get_glyph_id(0x41) == 7
    assert sub.get_glyph_id(0x43) == 9


def test_format_4_empty_after_only_terminator() -> None:
    # Only the 0xFFFF terminator: no real mappings; everything -> gid 0.
    segs = [(0xFFFF, 0xFFFF, 1, 0)]
    sub = _run(_build_format4(segs), num_glyphs=10)
    assert sub.get_glyph_id(0x41) == 0
    assert sub.get_char_codes(1) is None


# ---------------------------------------------------------------------------
# Format 6 (trimmed table)
# ---------------------------------------------------------------------------


def _build_format6(first_code: int, glyph_id_array: list[int]) -> bytes:
    payload = struct.pack(">HH", first_code, len(glyph_id_array))
    if glyph_id_array:
        payload += struct.pack(f">{len(glyph_id_array)}H", *glyph_id_array)
    return struct.pack(">HHH", 6, 0, 0) + payload


def test_format_6_trimmed_range() -> None:
    sub = _run(_build_format6(0x100, [3, 4, 5, 6]), num_glyphs=10)
    assert sub.get_glyph_id(0x100) == 3
    assert sub.get_glyph_id(0x101) == 4
    assert sub.get_glyph_id(0x103) == 6
    # below and above the trimmed range -> gid 0
    assert sub.get_glyph_id(0xFF) == 0
    assert sub.get_glyph_id(0x104) == 0
    assert sub.get_char_codes(5) == [0x102]


def test_format_6_single_entry() -> None:
    sub = _run(_build_format6(0x41, [9]), num_glyphs=20)
    assert sub.get_glyph_id(0x41) == 9
    assert sub.get_glyph_id(0x42) == 0


def test_format_6_empty_entry_count() -> None:
    # entryCount 0 -> early return, nothing mapped.
    sub = _run(_build_format6(0x41, []), num_glyphs=20)
    assert sub.get_glyph_id(0x41) == 0
    assert sub.get_char_codes(0) is None


def test_format_6_zero_gid_entries_preserved_in_forward_map() -> None:
    # Upstream format 6 stores every entry, including gid 0, without bounding.
    sub = _run(_build_format6(0x10, [0, 5, 0]), num_glyphs=20)
    assert sub.get_glyph_id(0x10) == 0
    assert sub.get_glyph_id(0x11) == 5
    assert sub.get_glyph_id(0x12) == 0


# ---------------------------------------------------------------------------
# Format 10 (trimmed 32-bit array)
# ---------------------------------------------------------------------------


def _build_format10(start_char_code: int, glyph_id_array: list[int]) -> bytes:
    # format(uint16=10), reserved(uint16), length(uint32), language(uint32),
    # startCharCode(uint32), numChars(uint32), glyphs(uint16 * numChars)
    payload = struct.pack(">II", start_char_code, len(glyph_id_array))
    if glyph_id_array:
        payload += struct.pack(f">{len(glyph_id_array)}H", *glyph_id_array)
    return struct.pack(">HHII", 10, 0, 0, 0) + payload


def test_format_10_trimmed_array() -> None:
    sub = _run(_build_format10(0x10000, [1, 2, 3]), num_glyphs=10)
    assert sub.get_glyph_id(0x10000) == 1
    assert sub.get_glyph_id(0x10001) == 2
    assert sub.get_glyph_id(0x10002) == 3
    assert sub.get_glyph_id(0x10003) == 0


def test_format_10_zero_gid_skipped() -> None:
    # gid 0 entries are skipped (continue), not stored.
    sub = _run(_build_format10(0x20, [0, 7, 0]), num_glyphs=10)
    assert sub.get_glyph_id(0x20) == 0
    assert sub.get_glyph_id(0x21) == 7
    assert sub.get_glyph_id(0x22) == 0


def test_format_10_out_of_range_gid_skipped() -> None:
    # gid >= num_glyphs is skipped.
    sub = _run(_build_format10(0x30, [5, 50]), num_glyphs=10)
    assert sub.get_glyph_id(0x30) == 5
    assert sub.get_glyph_id(0x31) == 0


# ---------------------------------------------------------------------------
# Format 12 (segmented coverage groups)
# ---------------------------------------------------------------------------


def _build_format12(groups: list[tuple[int, int, int]]) -> bytes:
    # format(uint16=12), reserved(uint16), length(uint32), language(uint32),
    # nGroups(uint32), groups(startCharCode, endCharCode, startGlyphID) uint32 x3
    payload = struct.pack(">I", len(groups))
    for first, end, start_glyph in groups:
        payload += struct.pack(">III", first, end, start_glyph)
    return struct.pack(">HHII", 12, 0, 0, 0) + payload


def test_format_12_group_inclusive_end() -> None:
    # endCharCode is INCLUSIVE: group 0x41..0x43 maps three codes.
    sub = _run(_build_format12([(0x41, 0x43, 1)]), num_glyphs=10)
    assert sub.get_glyph_id(0x41) == 1
    assert sub.get_glyph_id(0x42) == 2
    assert sub.get_glyph_id(0x43) == 3
    assert sub.get_glyph_id(0x44) == 0  # beyond inclusive end
    assert sub.get_glyph_id(0x40) == 0
    assert sub.get_char_codes(2) == [0x42]


def test_format_12_single_code_group() -> None:
    sub = _run(_build_format12([(0x100, 0x100, 9)]), num_glyphs=20)
    assert sub.get_glyph_id(0x100) == 9
    assert sub.get_glyph_id(0x101) == 0


def test_format_12_multiple_groups() -> None:
    groups = [(0x41, 0x42, 1), (0x61, 0x63, 10)]
    sub = _run(_build_format12(groups), num_glyphs=64)
    assert sub.get_glyph_id(0x41) == 1
    assert sub.get_glyph_id(0x42) == 2
    assert sub.get_glyph_id(0x61) == 10
    assert sub.get_glyph_id(0x63) == 12
    # gap
    assert sub.get_glyph_id(0x50) == 0


def test_format_12_supplementary_plane() -> None:
    sub = _run(_build_format12([(0x10000, 0x10002, 5)]), num_glyphs=20)
    assert sub.get_glyph_id(0x10000) == 5
    assert sub.get_glyph_id(0x10002) == 7
    assert sub.get_glyph_id(0x10003) == 0


def test_format_12_glyph_index_beyond_num_glyphs_breaks() -> None:
    # start_glyph 8, group of 4 codes, num_glyphs 10 -> only first two valid;
    # the loop BREAKS at the first invalid glyph index.
    sub = _run(_build_format12([(0x41, 0x44, 8)]), num_glyphs=10)
    assert sub.get_glyph_id(0x41) == 8
    assert sub.get_glyph_id(0x42) == 9
    assert sub.get_glyph_id(0x43) == 0
    assert sub.get_glyph_id(0x44) == 0


def test_format_12_invalid_first_code_raises() -> None:
    # firstCode in the surrogate range -> OSError.
    with pytest.raises(OSError):
        _run(_build_format12([(0xD800, 0xD801, 1)]), num_glyphs=10)


def test_format_12_end_before_first_raises() -> None:
    with pytest.raises(OSError):
        _run(_build_format12([(0x50, 0x40, 1)]), num_glyphs=10)


# ---------------------------------------------------------------------------
# Cross-format: uncovered codes always resolve to gid 0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "builder",
    [
        lambda: _build_format4([(0x41, 0x42, 0, 0), (0xFFFF, 0xFFFF, 1, 0)]),
        lambda: _build_format6(0x41, [1, 2]),
        lambda: _build_format12([(0x41, 0x42, 1)]),
    ],
    ids=["format4", "format6", "format12"],
)
def test_uncovered_code_maps_to_gid_zero(builder) -> None:
    sub = _run(builder(), num_glyphs=64)
    assert sub.get_glyph_id(0x00) == 0
    assert sub.get_glyph_id(0x99) == 0
    assert sub.get_glyph_id(0xFFFE) == 0


# ---------------------------------------------------------------------------
# Reverse map: multiple codes -> same gid funnel through the multimap
# ---------------------------------------------------------------------------


def test_reverse_map_multiple_codes_same_gid() -> None:
    # Two format-12 groups whose codes both resolve to gid 5.
    groups = [(0x41, 0x41, 5), (0x61, 0x61, 5)]
    sub = _run(_build_format12(groups), num_glyphs=20)
    assert sub.get_glyph_id(0x41) == 5
    assert sub.get_glyph_id(0x61) == 5
    codes = sub.get_char_codes(5)
    assert codes is not None
    assert sorted(codes) == [0x41, 0x61]


def test_get_char_code_out_of_range_returns_minus_one() -> None:
    sub = _run(_build_format6(0x41, [1, 2]), num_glyphs=10)
    assert sub.get_char_code(-1) == -1
    assert sub.get_char_code(10_000) == -1
    assert sub.get_char_codes(10_000) is None

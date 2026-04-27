"""Hand-written tests for OpenType cmap subtable formats 8, 10, 13, 14.

Formats 0/2/4/6/12 already have coverage in ``test_cmap_subtable.py``; this
file fills out the round-out done in fontbox cluster #2 — the higher-format
parsers added so we can read full-Unicode and DBCS-legacy fonts without
falling back to ``NotImplementedError``.

Each test builds a synthetic byte stream conforming to the OpenType ``cmap``
spec and feeds it through ``CmapSubtable.init_subtable``.
"""
from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _CmapStub:
    """Minimal stand-in for ``CmapTable`` — only exposes ``get_offset()``."""

    def __init__(self, offset: int = 0) -> None:
        self._offset = offset

    def get_offset(self) -> int:
        return self._offset


# Helper: assemble the common >=8 subtable header (format word + reserved +
# length + language). The actual values for length/language don't influence
# parsing — they're only consumed.
def _hdr_ge8(format_id: int) -> bytes:
    return struct.pack(">HHII", format_id, 0, 0, 0)


# ---------------------------------------------------------------------------
# Format 8 (mixed 16-/32-bit coverage)
# ---------------------------------------------------------------------------


def _build_format8(groups: list[tuple[int, int, int]]) -> bytes:
    # is32 (8192 bytes) + nGroups (uint32) + groups (uint32 x3)
    is32 = b"\x00" * 8192
    payload = is32 + struct.pack(">I", len(groups))
    for first, end, start_glyph in groups:
        payload += struct.pack(">III", first, end, start_glyph)
    return _hdr_ge8(8) + payload


def test_format_8_simple_group_round_trips() -> None:
    blob = _build_format8([(0x41, 0x43, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)
    assert sub.get_glyph_id(0x41) == 1
    assert sub.get_glyph_id(0x42) == 2
    assert sub.get_glyph_id(0x43) == 3
    assert sub.get_glyph_id(0x40) == 0
    assert sub.get_char_codes(2) == [0x42]


def test_format_8_supplementary_plane() -> None:
    blob = _build_format8([(0x10000, 0x10001, 5)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)
    assert sub.get_glyph_id(0x10000) == 5
    assert sub.get_glyph_id(0x10001) == 6


def test_format_8_invalid_first_code_raises() -> None:
    blob = _build_format8([(0xD800, 0xD801, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    with pytest.raises(OSError):
        sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)


def test_format_8_glyph_index_beyond_num_glyphs_truncates() -> None:
    # start_glyph=8, range covers 4 codes, but num_glyphs=10 → only 8,9 valid.
    blob = _build_format8([(0x41, 0x44, 8)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)
    assert sub.get_glyph_id(0x41) == 8
    assert sub.get_glyph_id(0x42) == 9
    # 0x43 and 0x44 would map to gids 10 and 11 — invalid.
    assert sub.get_glyph_id(0x43) == 0
    assert sub.get_glyph_id(0x44) == 0


# ---------------------------------------------------------------------------
# Format 10 (trimmed array — UCS-4)
# ---------------------------------------------------------------------------


def _build_format10(start_char: int, glyph_array: list[int]) -> bytes:
    # startCharCode (uint32), numChars (uint32), glyphArray (uint16 * numChars)
    payload = struct.pack(">II", start_char, len(glyph_array))
    if glyph_array:
        payload += struct.pack(f">{len(glyph_array)}H", *glyph_array)
    return _hdr_ge8(10) + payload


def test_format_10_trimmed_array_round_trip() -> None:
    blob = _build_format10(0x10000, [1, 2, 3, 4])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)
    assert sub.get_glyph_id(0x10000) == 1
    assert sub.get_glyph_id(0x10001) == 2
    assert sub.get_glyph_id(0x10002) == 3
    assert sub.get_glyph_id(0x10003) == 4
    assert sub.get_glyph_id(0x10004) == 0
    assert sub.get_char_codes(3) == [0x10002]


def test_format_10_skips_zero_glyphs() -> None:
    # gid=0 means "no mapping" — should not enter the dict.
    blob = _build_format10(0x100, [0, 7, 0, 8])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)
    assert sub.get_glyph_id(0x100) == 0
    assert sub.get_glyph_id(0x101) == 7
    assert sub.get_glyph_id(0x102) == 0
    assert sub.get_glyph_id(0x103) == 8


def test_format_10_zero_chars_does_not_crash() -> None:
    blob = _build_format10(0x100, [])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=0, data=data)
    assert sub.get_glyph_id(0x100) == 0


def test_format_10_invalid_glyph_index_skipped() -> None:
    # num_glyphs=5, glyph_array contains 99 → ignored.
    blob = _build_format10(0x100, [1, 99, 3])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=5, data=data)
    assert sub.get_glyph_id(0x100) == 1
    assert sub.get_glyph_id(0x101) == 0  # invalid skipped
    assert sub.get_glyph_id(0x102) == 3


# ---------------------------------------------------------------------------
# Format 13 (many-to-one)
# ---------------------------------------------------------------------------


def _build_format13(groups: list[tuple[int, int, int]]) -> bytes:
    # nGroups (uint32) + groups (uint32 x3): startCharCode, endCharCode, glyphID
    payload = struct.pack(">I", len(groups))
    for first, end, glyph_id in groups:
        payload += struct.pack(">III", first, end, glyph_id)
    return _hdr_ge8(13) + payload


def test_format_13_many_to_one() -> None:
    # Codes 0xE000..0xE004 all map to glyph 1 (Last Resort behaviour).
    blob = _build_format13([(0xE000, 0xE004, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)
    for code in range(0xE000, 0xE005):
        assert sub.get_glyph_id(code) == 1
    # Reverse lookup must include all codes, sorted.
    assert sub.get_char_codes(1) == list(range(0xE000, 0xE005))


def test_format_13_multiple_groups() -> None:
    blob = _build_format13([
        (0x41, 0x42, 1),
        (0x50, 0x51, 2),
    ])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)
    assert sub.get_glyph_id(0x41) == 1
    assert sub.get_glyph_id(0x42) == 1
    assert sub.get_glyph_id(0x50) == 2
    assert sub.get_glyph_id(0x51) == 2
    assert sub.get_glyph_id(0x43) == 0


def test_format_13_invalid_first_code_raises() -> None:
    blob = _build_format13([(0xD800, 0xD801, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    with pytest.raises(OSError):
        sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)


def test_format_13_invalid_glyph_id_skipped() -> None:
    # glyph_id 99 >= num_glyphs 10 → group ignored.
    blob = _build_format13([(0x41, 0x42, 99), (0x50, 0x51, 3)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)
    assert sub.get_glyph_id(0x41) == 0
    assert sub.get_glyph_id(0x50) == 3


def test_format_13_zero_num_glyphs_returns() -> None:
    blob = _build_format13([(0x41, 0x42, 1)])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=0, data=data)
    assert sub.get_glyph_id(0x41) == 0


# ---------------------------------------------------------------------------
# Format 14 (Unicode Variation Sequences)
# ---------------------------------------------------------------------------


def _pack_uint24(value: int) -> bytes:
    return bytes([(value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF])


def _build_format14(
    records: list[tuple[int, list[tuple[int, int]] | None, list[tuple[int, int]] | None]],
) -> bytes:
    """Assemble a format-14 subtable.

    Each record is ``(varSelector, default_uvs_ranges, non_default_uvs_pairs)``:
      * default_uvs_ranges: list of (start_unicode, additional_count) — or None
        if no defaultUVS table for that selector.
      * non_default_uvs_pairs: list of (unicode, glyph_id) — or None.
    """
    # Header (after the 6 bytes already consumed by init_subtable):
    #   uint32 numVarSelectorRecords
    #   N * (uint24 varSelector, uint32 defaultUVSOffset, uint32 nonDefaultUVSOffset)
    n = len(records)
    header_size = 6  # format(uint16) + length(uint32)
    record_size = 11  # uint24 + uint32 + uint32
    records_table_size = n * record_size
    # Body chunks (default UVS table and non-default UVS table per record).
    body = b""
    record_offsets: list[tuple[int, int]] = []  # (default_off, non_default_off) per record
    cursor = header_size + 4 + records_table_size  # 4 = numVarSelectorRecords field
    for _, default_ranges, non_default_pairs in records:
        if default_ranges is not None:
            default_off = cursor
            chunk = struct.pack(">I", len(default_ranges))
            for start, additional in default_ranges:
                chunk += _pack_uint24(start) + bytes([additional])
            body += chunk
            cursor += len(chunk)
        else:
            default_off = 0
        if non_default_pairs is not None:
            non_default_off = cursor
            chunk = struct.pack(">I", len(non_default_pairs))
            for unicode_value, glyph_id in non_default_pairs:
                chunk += _pack_uint24(unicode_value) + struct.pack(">H", glyph_id)
            body += chunk
            cursor += len(chunk)
        else:
            non_default_off = 0
        record_offsets.append((default_off, non_default_off))

    total_length = cursor
    out = struct.pack(">HI", 14, total_length)
    out += struct.pack(">I", n)
    for (var_selector, _dr, _np), (default_off, non_default_off) in zip(
        records, record_offsets, strict=True
    ):
        out += _pack_uint24(var_selector)
        out += struct.pack(">II", default_off, non_default_off)
    out += body
    return out


def test_format_14_non_default_uvs_lookup() -> None:
    # Variation selector 0xFE00, base codepoint 0x4E00 → glyph 42.
    blob = _build_format14([
        (0xFE00, None, [(0x4E00, 42), (0x4E01, 43)]),
    ])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=100, data=data)
    assert sub.has_uvs()
    assert sub.get_glyph_id_uvs(0x4E00, 0xFE00) == 42
    assert sub.get_glyph_id_uvs(0x4E01, 0xFE00) == 43
    # Unknown pair → 0
    assert sub.get_glyph_id_uvs(0x4E02, 0xFE00) == 0
    assert sub.get_glyph_id_uvs(0x4E00, 0xFE01) == 0


def test_format_14_default_uvs_recorded() -> None:
    # Default UVS: codes [0x3000..0x3002] under selector 0xE0100 default to
    # the base glyph (lookup returns 0 — caller falls back to base cmap).
    blob = _build_format14([
        (0xE0100, [(0x3000, 2)], None),
    ])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=100, data=data)
    assert sub.has_uvs()
    # No non-default mappings => 0; default UVS doesn't override the base.
    assert sub.get_glyph_id_uvs(0x3000, 0xE0100) == 0
    assert sub.get_glyph_id_uvs(0x3002, 0xE0100) == 0


def test_format_14_mixed_default_and_non_default() -> None:
    blob = _build_format14([
        (0xFE00, [(0x2000, 1)], [(0x3000, 7)]),
        (0xFE01, None, [(0x3000, 8)]),
    ])
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=100, data=data)
    assert sub.get_glyph_id_uvs(0x3000, 0xFE00) == 7
    assert sub.get_glyph_id_uvs(0x3000, 0xFE01) == 8
    # Default UVS pair returns 0 (caller uses the base cmap fallback).
    assert sub.get_glyph_id_uvs(0x2000, 0xFE00) == 0
    # Format 14 doesn't populate the BMP codepoint→glyph dict.
    assert sub.get_glyph_id(0x3000) == 0


def test_format_14_no_uvs_state_when_not_format_14() -> None:
    # A format-6 subtable should report has_uvs() == False.
    payload = struct.pack(">HH", 0x30, 1) + struct.pack(">H", 7)
    blob = struct.pack(">HHH", 6, 0, 0) + payload
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    sub.init_subtable(_CmapStub(), num_glyphs=10, data=data)
    assert not sub.has_uvs()


# ---------------------------------------------------------------------------
# Sanity: init_subtable header consumes the right number of bytes per format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "build,format_id",
    [
        (lambda: _build_format8([(0x41, 0x41, 1)]), 8),
        (lambda: _build_format10(0x100, [1]), 10),
        (lambda: _build_format13([(0x41, 0x41, 1)]), 13),
    ],
)
def test_format_ge8_header_consumed(build: object, format_id: int) -> None:
    blob = build()  # type: ignore[operator]
    data = MemoryTTFDataStream(blob)
    sub = CmapSubtable()
    # Should not raise EOF; round-trip the one mapping.
    sub.init_subtable(_CmapStub(), num_glyphs=20, data=data)
    # Each builder above maps at least one code to a non-zero gid.
    assert any(
        sub.get_glyph_id(c) != 0 for c in (0x41, 0x100)
    ), f"no mapping for format {format_id}"

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, cast

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

if TYPE_CHECKING:
    from pypdfbox.fontbox.ttf.cmap_table import CmapTable


class _CmapStub:
    def get_offset(self) -> int:
        return 0


def _format4_subtable(
    start_count: list[int],
    end_count: list[int],
    id_delta: list[int],
    id_range_offset: list[int],
    glyph_id_array: list[int] | None = None,
) -> bytes:
    seg_count = len(start_count)
    payload = struct.pack(">H", seg_count * 2)
    payload += struct.pack(">HHH", 0, 0, 0)
    payload += struct.pack(f">{seg_count}H", *end_count)
    payload += struct.pack(">H", 0)
    payload += struct.pack(f">{seg_count}H", *start_count)
    payload += struct.pack(f">{seg_count}H", *id_delta)
    payload += struct.pack(f">{seg_count}H", *id_range_offset)
    if glyph_id_array:
        payload += struct.pack(f">{len(glyph_id_array)}H", *glyph_id_array)
    return struct.pack(">HHH", 4, len(payload) + 6, 0) + payload


def test_wave300_format4_ignores_direct_glyph_id_beyond_num_glyphs() -> None:
    blob = _format4_subtable(
        start_count=[0x0041, 0xFFFF],
        end_count=[0x0042, 0xFFFF],
        id_delta=[0x0001, 0x0001],
        id_range_offset=[0, 0],
    )
    subtable = CmapSubtable()

    subtable.init_subtable(
        cast("CmapTable", _CmapStub()),
        num_glyphs=0x43,
        data=MemoryTTFDataStream(blob),
    )

    assert subtable.get_glyph_id(0x0041) == 0x0042
    assert subtable.get_glyph_id(0x0042) == 0
    assert subtable.get_char_codes(0x0042) == [0x0041]
    assert subtable.get_char_codes(0x0043) is None


def test_wave300_format4_ignores_array_glyph_id_beyond_num_glyphs() -> None:
    blob = _format4_subtable(
        start_count=[0x0041, 0xFFFF],
        end_count=[0x0042, 0xFFFF],
        id_delta=[0x0000, 0x0001],
        id_range_offset=[4, 0],
        glyph_id_array=[5, 6],
    )
    subtable = CmapSubtable()

    subtable.init_subtable(
        cast("CmapTable", _CmapStub()),
        num_glyphs=6,
        data=MemoryTTFDataStream(blob),
    )

    assert subtable.get_glyph_id(0x0041) == 5
    assert subtable.get_glyph_id(0x0042) == 0
    assert subtable.get_char_codes(5) == [0x0041]
    assert subtable.get_char_codes(6) is None

from __future__ import annotations

import logging
import struct

import pytest

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _CmapStub:
    def __init__(self, offset: int = 0) -> None:
        self._offset = offset

    def get_offset(self) -> int:
        return self._offset


def _format6(first_code: int, glyph_ids: list[int]) -> bytes:
    payload = struct.pack(">HH", first_code, len(glyph_ids))
    if glyph_ids:
        payload += struct.pack(f">{len(glyph_ids)}H", *glyph_ids)
    return struct.pack(">HHH", 6, len(payload) + 6, 0) + payload


def _format2(
    first_code: int,
    glyph_ids: list[int],
    *,
    id_delta: int = 0,
    num_subheaders: int = 1,
) -> bytes:
    sub_header_keys = [0] * 256
    max_sub_header_index = num_subheaders - 1
    if max_sub_header_index:
        sub_header_keys[1] = max_sub_header_index * 8
    payload = struct.pack(">256H", *sub_header_keys)
    for i in range(num_subheaders):
        if i == max_sub_header_index:
            raw_range_offset = (num_subheaders - i - 1) * 8 + 2
            payload += struct.pack(
                ">HHhH", first_code, len(glyph_ids), id_delta, raw_range_offset
            )
        else:
            payload += struct.pack(">HHhH", 0, 0, 0, 2)
    if glyph_ids:
        payload += struct.pack(f">{len(glyph_ids)}H", *glyph_ids)
    return struct.pack(">HHH", 2, len(payload) + 6, 0) + payload


def _hdr_ge8(format_id: int) -> bytes:
    return struct.pack(">HHII", format_id, 0, 0, 0)


def _format8(groups: list[tuple[int, int, int]]) -> bytes:
    payload = b"\x00" * 8192 + struct.pack(">I", len(groups))
    for first, end, start_glyph in groups:
        payload += struct.pack(">III", first, end, start_glyph)
    return _hdr_ge8(8) + payload


def _format12(groups: list[tuple[int, int, int]]) -> bytes:
    payload = struct.pack(">I", len(groups))
    for first, end, start_glyph in groups:
        payload += struct.pack(">III", first, end, start_glyph)
    return _hdr_ge8(12) + payload


def _format13(groups: list[tuple[int, int, int]]) -> bytes:
    payload = struct.pack(">I", len(groups))
    for first, end, glyph_id in groups:
        payload += struct.pack(">III", first, end, glyph_id)
    return _hdr_ge8(13) + payload


def test_wave398_init_subtable_uses_cmap_and_record_offsets() -> None:
    subtable = CmapSubtable()
    subtable.init_data(MemoryTTFDataStream(struct.pack(">HHI", 3, 1, 4)))
    data = MemoryTTFDataStream(b"\x00" * 10 + _format6(0x30, [7]))

    subtable.init_subtable(_CmapStub(offset=6), num_glyphs=10, data=data)

    assert subtable.get_platform_id() == 3
    assert subtable.get_platform_encoding_id() == 1
    assert subtable.get_glyph_id(0x30) == 7
    assert subtable.get_char_codes(7) == [0x30]


def test_wave398_format2_maps_through_signed_delta_and_subheader_offset() -> None:
    blob = _format2(0x20, [5, 6], id_delta=-4, num_subheaders=2)
    subtable = CmapSubtable()

    subtable.init_subtable(_CmapStub(), num_glyphs=10, data=MemoryTTFDataStream(blob))

    assert subtable.get_glyph_id(0x120) == 1
    assert subtable.get_glyph_id(0x121) == 2
    assert subtable.get_char_codes(1) == [0x120]
    assert subtable.get_char_codes(2) == [0x121]


def test_wave398_format2_skips_invalid_glyph_and_keeps_valid_neighbors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable")
    blob = _format2(0x41, [1, 99, 3])
    subtable = CmapSubtable()

    subtable.init_subtable(_CmapStub(), num_glyphs=5, data=MemoryTTFDataStream(blob))

    assert subtable.get_glyph_id(0x41) == 1
    assert subtable.get_glyph_id(0x42) == 0
    assert subtable.get_glyph_id(0x43) == 3
    assert "glyphId 99 for charcode 66 ignored" in caplog.text


def test_wave398_format2_zero_glyph_font_logs_and_returns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable")
    blob = _format2(0x41, [1])
    subtable = CmapSubtable()

    subtable.init_subtable(_CmapStub(), num_glyphs=0, data=MemoryTTFDataStream(blob))

    assert subtable.get_glyph_id(0x41) == 0
    assert subtable.get_char_codes(0) is None
    assert "subtable has no glyphs" in caplog.text


def test_wave398_format4_only_terminator_logs_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable")
    payload = struct.pack(">HHHHHHHH", 2, 0, 0, 0, 0xFFFF, 0, 0xFFFF, 1)
    payload += struct.pack(">H", 0)
    blob = struct.pack(">HHH", 4, len(payload) + 6, 0) + payload
    subtable = CmapSubtable()

    subtable.init_subtable(_CmapStub(), num_glyphs=10, data=MemoryTTFDataStream(blob))

    assert subtable.get_glyph_id(0x41) == 0
    assert subtable.get_char_codes(0) is None
    assert "cmap format 4 subtable is empty" in caplog.text


def test_wave398_format10_all_invalid_glyphs_leave_reverse_lookup_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable")
    payload = struct.pack(">IIHH", 0x10000, 2, 20, 21)
    blob = _hdr_ge8(10) + payload
    subtable = CmapSubtable()

    subtable.init_subtable(_CmapStub(), num_glyphs=20, data=MemoryTTFDataStream(blob))

    assert subtable.get_glyph_id(0x10000) == 0
    assert subtable.get_glyph_id(0x10001) == 0
    assert subtable.get_char_codes(20) is None
    assert "Format 10 cmap contains an invalid glyph index" in caplog.text


@pytest.mark.parametrize(
    "blob",
    [
        _format8([(0x43, 0x41, 1)]),
        _format12([(0x43, 0x41, 1)]),
        _format13([(0x43, 0x41, 1)]),
    ],
    ids=["format8", "format12", "format13"],
)
def test_wave398_segmented_formats_reject_end_before_start(blob: bytes) -> None:
    subtable = CmapSubtable()

    with pytest.raises(OSError, match="Invalid character code 0x41"):
        subtable.init_subtable(_CmapStub(), num_glyphs=10, data=MemoryTTFDataStream(blob))


@pytest.mark.parametrize(
    "blob",
    [
        _format8([(0x41, 0xD800, 1)]),
        _format12([(0x41, 0xD800, 1)]),
        _format13([(0x41, 0xD800, 1)]),
    ],
    ids=["format8", "format12", "format13"],
)
def test_wave398_segmented_formats_reject_surrogate_end_code(blob: bytes) -> None:
    subtable = CmapSubtable()

    with pytest.raises(OSError, match="Invalid character code 0xD800"):
        subtable.init_subtable(_CmapStub(), num_glyphs=10, data=MemoryTTFDataStream(blob))

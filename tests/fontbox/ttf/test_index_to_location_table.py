from __future__ import annotations

import struct
from dataclasses import dataclass

import pytest

from pypdfbox.fontbox.ttf.index_to_location_table import IndexToLocationTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


@dataclass
class _StubHead:
    index_to_loc_format: int

    def get_index_to_loc_format(self) -> int:
        return self.index_to_loc_format


@dataclass
class _StubTTF:
    num_glyphs: int
    head: _StubHead | None

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs

    def get_header(self) -> _StubHead | None:
        return self.head


def test_read_short_offsets() -> None:
    # short format stores offset/2 as uint16; read() multiplies by 2
    raw_short = [0, 50, 100, 250]
    blob = b"".join(struct.pack(">H", v) for v in raw_short)
    table = IndexToLocationTable()
    table.read(_StubTTF(num_glyphs=3, head=_StubHead(index_to_loc_format=0)),
               MemoryTTFDataStream(blob))
    assert table.get_initialized() is True
    assert table.get_offsets() == [0, 100, 200, 500]


def test_read_long_offsets() -> None:
    raw_long = [0, 1024, 2048, 100_000]
    blob = b"".join(struct.pack(">I", v) for v in raw_long)
    table = IndexToLocationTable()
    table.read(_StubTTF(num_glyphs=3, head=_StubHead(index_to_loc_format=1)),
               MemoryTTFDataStream(blob))
    assert table.get_offsets() == raw_long


def test_read_raises_when_head_missing() -> None:
    table = IndexToLocationTable()
    with pytest.raises(OSError, match="Could not get head table"):
        table.read(_StubTTF(num_glyphs=1, head=None),
                   MemoryTTFDataStream(b""))


def test_read_unknown_format_raises() -> None:
    blob = struct.pack(">H", 0) * 2
    table = IndexToLocationTable()
    with pytest.raises(OSError, match="unknown offset format"):
        table.read(_StubTTF(num_glyphs=1, head=_StubHead(index_to_loc_format=42)),
                   MemoryTTFDataStream(blob))


def test_pdfbox_5794_empty_glyph_short() -> None:
    # num_glyphs == 1, both offsets zero -> bail out with "no glyphs"
    blob = struct.pack(">HH", 0, 0)
    table = IndexToLocationTable()
    with pytest.raises(OSError, match="no glyphs"):
        table.read(_StubTTF(num_glyphs=1, head=_StubHead(index_to_loc_format=0)),
                   MemoryTTFDataStream(blob))


def test_pdfbox_5794_empty_glyph_long() -> None:
    blob = struct.pack(">II", 0, 0)
    table = IndexToLocationTable()
    with pytest.raises(OSError, match="no glyphs"):
        table.read(_StubTTF(num_glyphs=1, head=_StubHead(index_to_loc_format=1)),
                   MemoryTTFDataStream(blob))


def test_one_glyph_nonzero_offset_does_not_raise() -> None:
    # only triggers raise when both [0] and [1] are zero
    blob = struct.pack(">HH", 0, 5)
    table = IndexToLocationTable()
    table.read(_StubTTF(num_glyphs=1, head=_StubHead(index_to_loc_format=0)),
               MemoryTTFDataStream(blob))
    assert table.get_offsets() == [0, 10]


def test_zero_glyphs_is_legal_and_yields_single_zero_offset() -> None:
    # num_glyphs==0 means we read one offset (the trailing sentinel)
    blob = struct.pack(">H", 0)
    table = IndexToLocationTable()
    table.read(_StubTTF(num_glyphs=0, head=_StubHead(index_to_loc_format=0)),
               MemoryTTFDataStream(blob))
    assert table.get_offsets() == [0]


def test_set_offsets_round_trip() -> None:
    table = IndexToLocationTable()
    table.set_offsets([0, 10, 20])
    assert table.get_offsets() == [0, 10, 20]


def test_long_offsets_full_uint32_range() -> None:
    blob = struct.pack(">II", 0, 0xFFFFFFFE)
    table = IndexToLocationTable()
    table.read(_StubTTF(num_glyphs=1, head=_StubHead(index_to_loc_format=1)),
               MemoryTTFDataStream(blob))
    assert table.get_offsets() == [0, 0xFFFFFFFE]

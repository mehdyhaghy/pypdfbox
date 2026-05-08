from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from pypdfbox.fontbox.ttf.index_to_location_table import IndexToLocationTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

if TYPE_CHECKING:
    from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont


@dataclass
class _StubHead:
    index_to_loc_format: int

    def get_index_to_loc_format(self) -> int:
        return self.index_to_loc_format


@dataclass
class _StubTTF:
    num_glyphs: int
    head: _StubHead

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs

    def get_header(self) -> _StubHead:
        return self.head


def _ttf(num_glyphs: int, index_to_loc_format: int) -> TrueTypeFont:
    return cast(
        "TrueTypeFont",
        _StubTTF(
            num_glyphs=num_glyphs,
            head=_StubHead(index_to_loc_format=index_to_loc_format),
        ),
    )


def test_short_loca_decreasing_offsets_raise_oserror() -> None:
    blob = struct.pack(">HHH", 10, 8, 12)
    table = IndexToLocationTable()

    with pytest.raises(OSError, match="decreasing offsets"):
        table.read(
            _ttf(num_glyphs=2, index_to_loc_format=0),
            MemoryTTFDataStream(blob),
        )

    assert table.get_initialized() is False


def test_long_loca_equal_offsets_remain_valid_for_empty_glyphs() -> None:
    blob = struct.pack(">III", 0, 0, 20)
    table = IndexToLocationTable()

    table.read(
        _ttf(num_glyphs=2, index_to_loc_format=1),
        MemoryTTFDataStream(blob),
    )

    assert table.get_initialized() is True
    assert table.get_offsets() == [0, 0, 20]

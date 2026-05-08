from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.vertical_metrics_table import VerticalMetricsTable

if TYPE_CHECKING:
    from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont


@dataclass
class _StubVHEA:
    num_v_metrics: int

    def get_number_of_v_metrics(self) -> int:
        return self.num_v_metrics


@dataclass
class _StubTTF:
    num_glyphs: int
    v_header: _StubVHEA

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs

    def get_vertical_header(self) -> _StubVHEA:
        return self.v_header


def _ttf(num_glyphs: int, num_v_metrics: int) -> TrueTypeFont:
    return cast(
        "TrueTypeFont",
        _StubTTF(num_glyphs=num_glyphs, v_header=_StubVHEA(num_v_metrics)),
    )


def _pack_metric(advance: int, tsb: int) -> bytes:
    return struct.pack(">Hh", advance, tsb)


def _pack_tsb(tsb: int) -> bytes:
    return struct.pack(">h", tsb)


def test_missing_vertical_tsb_array_is_zero_padded() -> None:
    table = VerticalMetricsTable()
    blob = _pack_metric(1000, 25)
    table.set_length(len(blob))

    table.read(_ttf(num_glyphs=4, num_v_metrics=1), MemoryTTFDataStream(blob))

    assert table.get_advance_height(3) == 1000
    assert table.get_top_side_bearing(0) == 25
    assert table.get_top_side_bearing(1) == 0
    assert table.get_top_side_bearing(2) == 0
    assert table.get_top_side_bearing(3) == 0


def test_truncated_vertical_tsb_array_is_zero_padded() -> None:
    table = VerticalMetricsTable()
    blob = _pack_metric(900, -12) + _pack_tsb(7)
    table.set_length(len(blob))

    table.read(_ttf(num_glyphs=4, num_v_metrics=1), MemoryTTFDataStream(blob))

    assert table.get_top_side_bearing(0) == -12
    assert table.get_top_side_bearing(1) == 7
    assert table.get_top_side_bearing(2) == 0
    assert table.get_top_side_bearing(3) == 0

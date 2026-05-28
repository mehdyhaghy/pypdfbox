from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import cast

import pytest

from pypdfbox.fontbox.ttf.horizontal_metrics_table import HorizontalMetricsTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


@dataclass
class _StubHHEA:
    num_h_metrics: int

    def get_number_of_h_metrics(self) -> int:
        return self.num_h_metrics


@dataclass
class _StubTTF:
    num_glyphs: int
    h_header: _StubHHEA | None

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs

    def get_horizontal_header(self) -> _StubHHEA | None:
        return self.h_header


def _as_ttf(stub: _StubTTF) -> TrueTypeFont:
    return cast(TrueTypeFont, stub)


def _pack_metric(advance: int, lsb: int) -> bytes:
    return struct.pack(">Hh", advance, lsb)


def _pack_lsb(lsb: int) -> bytes:
    return struct.pack(">h", lsb)


def test_read_basic_h_metrics_only() -> None:
    # 3 glyphs, all have a full hMetric (no trailing LSB array)
    blob = b"".join([
        _pack_metric(500, 10),
        _pack_metric(600, -5),
        _pack_metric(700, 0),
    ])
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _as_ttf(_StubTTF(num_glyphs=3, h_header=_StubHHEA(num_h_metrics=3))),
        MemoryTTFDataStream(blob),
    )

    assert table.get_initialized() is True
    assert table.get_advance_width(0) == 500
    assert table.get_advance_width(1) == 600
    assert table.get_advance_width(2) == 700
    assert table.get_left_side_bearing(0) == 10
    assert table.get_left_side_bearing(1) == -5
    assert table.get_left_side_bearing(2) == 0


def test_read_with_trailing_lsb_array() -> None:
    # 2 hMetrics + 3 trailing LSBs (monospaced font: 5 glyphs, 2 hMetrics)
    blob = b"".join([
        _pack_metric(500, 10),
        _pack_metric(600, -5),
        _pack_lsb(11),
        _pack_lsb(12),
        _pack_lsb(-13),
    ])
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _as_ttf(_StubTTF(num_glyphs=5, h_header=_StubHHEA(num_h_metrics=2))),
        MemoryTTFDataStream(blob),
    )

    # advance widths fall back to last-defined for gids >= num_h_metrics
    assert table.get_advance_width(0) == 500
    assert table.get_advance_width(1) == 600
    assert table.get_advance_width(2) == 600
    assert table.get_advance_width(4) == 600

    # LSBs come from the dedicated array for gids >= num_h_metrics
    assert table.get_left_side_bearing(0) == 10
    assert table.get_left_side_bearing(1) == -5
    assert table.get_left_side_bearing(2) == 11
    assert table.get_left_side_bearing(3) == 12
    assert table.get_left_side_bearing(4) == -13


def test_read_raises_when_no_horizontal_header() -> None:
    table = HorizontalMetricsTable()
    table.set_length(0)
    with pytest.raises(OSError, match="Could not get hmtx table"):
        table.read(_as_ttf(_StubTTF(num_glyphs=1, h_header=None)), MemoryTTFDataStream(b""))


def test_read_handles_bad_font_too_many_h_metrics() -> None:
    # numHMetrics > numGlyphs — should not crash and should allocate
    # a non-horizontal LSB array sized to num_glyphs.
    blob = _pack_metric(500, 10) + _pack_metric(600, -5)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _as_ttf(_StubTTF(num_glyphs=1, h_header=_StubHHEA(num_h_metrics=2))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_advance_width(0) == 500
    # gid==1 falls back to last defined entry, since 1 == num_h_metrics-1 still
    # within array; for clarity check gid=2 too
    assert table.get_advance_width(5) == 600


def test_read_truncated_lsb_array_pads_with_zeros() -> None:
    # 1 hMetric + claim of 3 trailing LSBs but only 1 actually present.
    # The for-loop guards on get_length(), so unsupplied entries stay 0.
    blob = _pack_metric(500, 10) + _pack_lsb(7)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _as_ttf(_StubTTF(num_glyphs=4, h_header=_StubHHEA(num_h_metrics=1))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_left_side_bearing(0) == 10
    assert table.get_left_side_bearing(1) == 7
    assert table.get_left_side_bearing(2) == 0
    assert table.get_left_side_bearing(3) == 0


def test_get_advance_width_empty_returns_default() -> None:
    table = HorizontalMetricsTable()
    # never called read(); _advance_width is empty
    assert table.get_advance_width(0) == 250
    assert table.get_advance_width(99) == 250


def test_get_left_side_bearing_empty_returns_zero() -> None:
    table = HorizontalMetricsTable()
    assert table.get_left_side_bearing(0) == 0


def test_invalid_negative_gid_does_not_use_python_negative_indexing() -> None:
    # Upstream indexes the metric arrays directly, so a negative gid throws
    # ArrayIndexOutOfBounds in Java. We mirror that by raising IndexError rather
    # than wrapping to the last element via Python negative indexing (verified
    # against PDFBox 3.0.7 by the HmtxLsbProbe oracle).
    blob = _pack_metric(500, 10) + _pack_metric(600, -5)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _as_ttf(_StubTTF(num_glyphs=2, h_header=_StubHHEA(num_h_metrics=2))),
        MemoryTTFDataStream(blob),
    )

    with pytest.raises(IndexError):
        table.get_advance_width(-1)
    with pytest.raises(IndexError):
        table.get_left_side_bearing(-1)


def test_get_left_side_bearing_beyond_available_lsb_throws() -> None:
    # gid >= numHMetrics indexes the trailing LSB-only array with no bounds
    # check upstream; an out-of-range gid throws ArrayIndexOutOfBounds in Java,
    # which we mirror as an IndexError (verified against PDFBox 3.0.7 by the
    # HmtxLsbProbe oracle — out-of-range GIDs emit ERR on both sides).
    blob = _pack_metric(500, 10) + _pack_lsb(7)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _as_ttf(_StubTTF(num_glyphs=2, h_header=_StubHHEA(num_h_metrics=1))),
        MemoryTTFDataStream(blob),
    )

    assert table.get_left_side_bearing(1) == 7
    with pytest.raises(IndexError):
        table.get_left_side_bearing(2)
    with pytest.raises(IndexError):
        table.get_left_side_bearing(99)


def test_signed_lsb_two_complement() -> None:
    blob = _pack_metric(1000, -32768) + _pack_metric(1000, 32767)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _as_ttf(_StubTTF(num_glyphs=2, h_header=_StubHHEA(num_h_metrics=2))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_left_side_bearing(0) == -32768
    assert table.get_left_side_bearing(1) == 32767

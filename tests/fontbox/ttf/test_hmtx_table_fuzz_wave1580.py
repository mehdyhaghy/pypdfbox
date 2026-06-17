"""Wave 1580 (Agent C) — fuzz the TrueType ``hmtx`` / ``hhea`` tables for
behavioral parity with Apache PDFBox 3.0.7
(``org.apache.fontbox.ttf.HorizontalMetricsTable`` /
``HorizontalHeaderTable``).

Focus areas:
  * ``get_advance_width(gid)`` for ``gid < numberOfHMetrics`` (own width) vs
    ``gid >= numberOfHMetrics`` — the monospace-tail optimization: such GIDs
    MUST clamp to the LAST full metric's advance width.
  * ``get_left_side_bearing(gid)`` for both regions: the trailing LSB-only
    array indexed at ``gid - numberOfHMetrics`` for GIDs beyond the full
    metrics.
  * ``numberOfHMetrics == numGlyphs`` (no trailing array) and
    ``numberOfHMetrics == 1`` (all glyphs share one width).
  * boundary GID ``gid == numberOfHMetrics`` (else branch).
  * out-of-range / negative GIDs (upstream array-index throw semantics).
  * ``hhea`` ascender / descender / lineGap / advanceWidthMax /
    minLeftSideBearing accessors over synthetic header bytes.

A pure-Python reference oracle mirrors upstream's exact branch structure so
fuzz inputs are checked against the Java semantics rather than against the
implementation under test.
"""

from __future__ import annotations

import random
import struct
from dataclasses import dataclass
from typing import cast

import pytest

from pypdfbox.fontbox.ttf.horizontal_header_table import HorizontalHeaderTable
from pypdfbox.fontbox.ttf.horizontal_metrics_table import HorizontalMetricsTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


# --------------------------------------------------------------------------
# stubs / builders
# --------------------------------------------------------------------------
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


def _build_table(
    *,
    metrics: list[tuple[int, int]],
    trailing_lsb: list[int],
    num_glyphs: int,
    declared_length: int | None = None,
) -> HorizontalMetricsTable:
    """Build a read() table from explicit full metrics + trailing LSBs."""
    blob = b"".join(_pack_metric(adv, lsb) for adv, lsb in metrics)
    blob += b"".join(_pack_lsb(v) for v in trailing_lsb)
    table = HorizontalMetricsTable()
    table.set_length(len(blob) if declared_length is None else declared_length)
    table.read(
        _as_ttf(_StubTTF(num_glyphs=num_glyphs, h_header=_StubHHEA(num_h_metrics=len(metrics)))),
        MemoryTTFDataStream(blob),
    )
    return table


# --------------------------------------------------------------------------
# reference oracle — mirrors upstream Java branch-for-branch
# --------------------------------------------------------------------------
def _ref_advance_width(advance_width: list[int], num_h_metrics: int, gid: int) -> int:
    if len(advance_width) == 0:
        return 250
    if gid < num_h_metrics:
        # Java: advanceWidth[gid] — throws for negative / oob.
        if gid < 0 or gid >= len(advance_width):
            raise IndexError(gid)
        return advance_width[gid]
    return advance_width[len(advance_width) - 1]


def _ref_left_side_bearing(
    lsb: list[int], non_horiz: list[int], num_h_metrics: int, gid: int
) -> int:
    if len(lsb) == 0:
        return 0
    if gid < num_h_metrics:
        if gid < 0 or gid >= len(lsb):
            raise IndexError(gid)
        return lsb[gid]
    idx = gid - num_h_metrics
    if idx < 0 or idx >= len(non_horiz):
        raise IndexError(gid)
    return non_horiz[idx]


# --------------------------------------------------------------------------
# hand-written targeted cases
# --------------------------------------------------------------------------
def test_all_full_metrics_no_trailing() -> None:
    # numberOfHMetrics == numGlyphs: every GID has its own width, no trailing.
    metrics = [(500, 10), (600, -5), (700, 0)]
    table = _build_table(metrics=metrics, trailing_lsb=[], num_glyphs=3)
    for gid, (adv, lsb) in enumerate(metrics):
        assert table.get_advance_width(gid) == adv
        assert table.get_left_side_bearing(gid) == lsb


def test_monospace_tail_clamps_to_last_advance() -> None:
    # 2 full metrics + 3 trailing LSBs; GIDs >= 2 clamp to the LAST advance.
    table = _build_table(
        metrics=[(500, 10), (600, -5)],
        trailing_lsb=[11, 12, -13],
        num_glyphs=5,
    )
    assert table.get_advance_width(0) == 500
    assert table.get_advance_width(1) == 600
    # the monospace-tail optimization: all beyond clamp to last (600), NOT 500.
    assert table.get_advance_width(2) == 600
    assert table.get_advance_width(3) == 600
    assert table.get_advance_width(4) == 600
    # LSBs for the tail come from the trailing array at (gid - numHMetrics).
    assert table.get_left_side_bearing(2) == 11
    assert table.get_left_side_bearing(3) == 12
    assert table.get_left_side_bearing(4) == -13


def test_boundary_gid_equals_num_h_metrics() -> None:
    # gid == numHMetrics hits the else branch on BOTH accessors.
    table = _build_table(
        metrics=[(400, 1), (800, 2)],
        trailing_lsb=[99],
        num_glyphs=3,
    )
    assert table.get_advance_width(2) == 800  # last full advance
    assert table.get_left_side_bearing(2) == 99  # trailing[0]


def test_num_h_metrics_one_all_share_one_width() -> None:
    # numberOfHMetrics == 1: a single advance for every glyph.
    table = _build_table(
        metrics=[(1000, 5)],
        trailing_lsb=[20, 21, 22, 23],
        num_glyphs=5,
    )
    for gid in range(5):
        assert table.get_advance_width(gid) == 1000
    assert table.get_left_side_bearing(0) == 5
    assert table.get_left_side_bearing(1) == 20
    assert table.get_left_side_bearing(4) == 23


def test_out_of_range_gid_in_full_region_does_not_wrap() -> None:
    # gid < numHMetrics but >= array length cannot happen normally (they are
    # equal), but a negative gid must throw rather than Python-wrap to the tail.
    table = _build_table(metrics=[(500, 10), (600, -5)], trailing_lsb=[], num_glyphs=2)
    with pytest.raises(IndexError):
        table.get_advance_width(-1)
    with pytest.raises(IndexError):
        table.get_left_side_bearing(-1)


def test_trailing_lsb_out_of_range_throws() -> None:
    table = _build_table(metrics=[(500, 10)], trailing_lsb=[7], num_glyphs=2)
    assert table.get_left_side_bearing(1) == 7
    with pytest.raises(IndexError):
        table.get_left_side_bearing(2)
    with pytest.raises(IndexError):
        table.get_left_side_bearing(500)


def test_empty_table_defaults() -> None:
    table = HorizontalMetricsTable()
    assert table.get_advance_width(0) == 250
    assert table.get_advance_width(123) == 250
    assert table.get_left_side_bearing(0) == 0
    assert table.get_left_side_bearing(123) == 0


def test_signed_lsb_extremes_and_unsigned_advance() -> None:
    # advance is unsigned (max 65535), lsb is signed two's-complement.
    table = _build_table(
        metrics=[(65535, -32768), (0, 32767)],
        trailing_lsb=[],
        num_glyphs=2,
    )
    assert table.get_advance_width(0) == 65535
    assert table.get_advance_width(1) == 0
    assert table.get_left_side_bearing(0) == -32768
    assert table.get_left_side_bearing(1) == 32767


def test_truncated_trailing_array_pads_zero() -> None:
    # declared length only covers 1 trailing lsb though numberNonHorizontal==3.
    blob = _pack_metric(500, 10) + _pack_lsb(7)
    table = HorizontalMetricsTable()
    table.set_length(len(blob))
    table.read(
        _as_ttf(_StubTTF(num_glyphs=4, h_header=_StubHHEA(num_h_metrics=1))),
        MemoryTTFDataStream(blob),
    )
    assert table.get_left_side_bearing(1) == 7
    assert table.get_left_side_bearing(2) == 0
    assert table.get_left_side_bearing(3) == 0


def test_bad_font_too_many_h_metrics() -> None:
    # numberOfHMetrics > numGlyphs: numberNonHorizontal clamps to numGlyphs.
    table = _build_table(
        metrics=[(500, 10), (600, -5)],
        trailing_lsb=[],
        num_glyphs=1,
    )
    assert table.get_advance_width(0) == 500
    assert table.get_advance_width(5) == 600  # clamps to last full advance


def test_read_raises_without_h_header() -> None:
    table = HorizontalMetricsTable()
    table.set_length(0)
    with pytest.raises(OSError, match="Could not get hmtx table"):
        table.read(_as_ttf(_StubTTF(num_glyphs=1, h_header=None)), MemoryTTFDataStream(b""))


# --------------------------------------------------------------------------
# hhea header
# --------------------------------------------------------------------------
def _build_hhea(
    *,
    ascender: int,
    descender: int,
    line_gap: int,
    advance_width_max: int,
    min_lsb: int,
    min_rsb: int,
    x_max_extent: int,
    num_h_metrics: int,
) -> HorizontalHeaderTable:
    blob = struct.pack(
        ">i hhh H hhh hh hhhhh h H",
        0x00010000,  # version 1.0 fixed
        ascender,
        descender,
        line_gap,
        advance_width_max,
        min_lsb,
        min_rsb,
        x_max_extent,
        0,  # caretSlopeRise
        0,  # caretSlopeRun
        0,  # reserved1..5
        0,
        0,
        0,
        0,
        0,  # metricDataFormat
        num_h_metrics,
    )
    table = HorizontalHeaderTable()
    table.set_length(len(blob))
    table.read(_as_ttf(_StubTTF(num_glyphs=0, h_header=None)), MemoryTTFDataStream(blob))
    return table


def test_hhea_accessors() -> None:
    hhea = _build_hhea(
        ascender=1500,
        descender=-400,
        line_gap=90,
        advance_width_max=2048,
        min_lsb=-150,
        min_rsb=-200,
        x_max_extent=1900,
        num_h_metrics=42,
    )
    assert hhea.get_version() == pytest.approx(1.0)
    assert hhea.get_ascender() == 1500
    assert hhea.get_descender() == -400
    assert hhea.get_line_gap() == 90
    assert hhea.get_advance_width_max() == 2048
    assert hhea.get_min_left_side_bearing() == -150
    assert hhea.get_min_right_side_bearing() == -200
    assert hhea.get_x_max_extent() == 1900
    assert hhea.get_number_of_h_metrics() == 42
    assert hhea.get_initialized() is True


def test_hhea_signed_fields_two_complement() -> None:
    hhea = _build_hhea(
        ascender=-1,
        descender=-32768,
        line_gap=-1,
        advance_width_max=65535,  # unsigned
        min_lsb=-32768,
        min_rsb=32767,
        x_max_extent=-5,
        num_h_metrics=65535,  # unsigned
    )
    assert hhea.get_ascender() == -1
    assert hhea.get_descender() == -32768
    assert hhea.get_line_gap() == -1
    assert hhea.get_advance_width_max() == 65535
    assert hhea.get_min_left_side_bearing() == -32768
    assert hhea.get_min_right_side_bearing() == 32767
    assert hhea.get_x_max_extent() == -5
    assert hhea.get_number_of_h_metrics() == 65535


# --------------------------------------------------------------------------
# randomized fuzz vs reference oracle
# --------------------------------------------------------------------------
@pytest.mark.parametrize("seed", list(range(24)))
def test_fuzz_against_reference_oracle(seed: int) -> None:
    rng = random.Random(seed)
    num_h_metrics = rng.randint(1, 8)
    # numGlyphs may be < (bad font), == , or > numHMetrics.
    num_glyphs = rng.randint(1, num_h_metrics + 8)

    metrics = [
        (rng.randint(0, 65535), rng.randint(-32768, 32767)) for _ in range(num_h_metrics)
    ]
    number_non_horizontal = num_glyphs - num_h_metrics
    if number_non_horizontal < 0:
        number_non_horizontal = num_glyphs
    trailing = [rng.randint(-32768, 32767) for _ in range(number_non_horizontal)]

    table = _build_table(metrics=metrics, trailing_lsb=trailing, num_glyphs=num_glyphs)

    advance_ref = [a for a, _ in metrics]
    lsb_ref = [b for _, b in metrics]

    # probe GIDs straddling every region: in-full, boundary, tail, out-of-range.
    probe_gids = list(range(num_glyphs + 4)) + [-1, num_h_metrics, num_h_metrics - 1]
    for gid in probe_gids:
        # advance width
        try:
            expected_adv = _ref_advance_width(advance_ref, num_h_metrics, gid)
        except IndexError:
            with pytest.raises(IndexError):
                table.get_advance_width(gid)
        else:
            assert table.get_advance_width(gid) == expected_adv

        # left side bearing
        try:
            expected_lsb = _ref_left_side_bearing(lsb_ref, trailing, num_h_metrics, gid)
        except IndexError:
            with pytest.raises(IndexError):
                table.get_left_side_bearing(gid)
        else:
            assert table.get_left_side_bearing(gid) == expected_lsb

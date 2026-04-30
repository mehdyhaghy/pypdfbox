from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.vertical_metrics_table import VerticalMetricsTable

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@dataclass
class _StubVHEA:
    num_v_metrics: int

    def get_number_of_v_metrics(self) -> int:
        return self.num_v_metrics


@dataclass
class _StubTTF:
    num_glyphs: int
    v_header: _StubVHEA | None

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs

    def get_vertical_header(self) -> _StubVHEA | None:
        return self.v_header


def _pack_metric(advance: int, tsb: int) -> bytes:
    return struct.pack(">Hh", advance, tsb)


def _pack_tsb(tsb: int) -> bytes:
    return struct.pack(">h", tsb)


def test_read_basic_v_metrics_only() -> None:
    # 3 glyphs, all carry a full vMetric (no trailing TSB array).
    blob = b"".join([
        _pack_metric(1000, 80),
        _pack_metric(900, -10),
        _pack_metric(1100, 0),
    ])
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(_StubTTF(num_glyphs=3, v_header=_StubVHEA(num_v_metrics=3)),
              MemoryTTFDataStream(blob))

    assert table.get_initialized() is True
    assert table.get_advance_height(0) == 1000
    assert table.get_advance_height(1) == 900
    assert table.get_advance_height(2) == 1100
    assert table.get_top_side_bearing(0) == 80
    assert table.get_top_side_bearing(1) == -10
    assert table.get_top_side_bearing(2) == 0


def test_read_with_trailing_tsb_array() -> None:
    # 2 vMetrics + 3 trailing TSBs (monospaced font: 5 glyphs, 2 vMetrics)
    blob = b"".join([
        _pack_metric(1000, 80),
        _pack_metric(900, -10),
        _pack_tsb(11),
        _pack_tsb(12),
        _pack_tsb(-13),
    ])
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(_StubTTF(num_glyphs=5, v_header=_StubVHEA(num_v_metrics=2)),
              MemoryTTFDataStream(blob))

    # advance heights fall back to last-defined for gids >= num_v_metrics
    assert table.get_advance_height(0) == 1000
    assert table.get_advance_height(1) == 900
    assert table.get_advance_height(2) == 900
    assert table.get_advance_height(4) == 900

    # TSBs come from the dedicated array for gids >= num_v_metrics
    assert table.get_top_side_bearing(0) == 80
    assert table.get_top_side_bearing(1) == -10
    assert table.get_top_side_bearing(2) == 11
    assert table.get_top_side_bearing(3) == 12
    assert table.get_top_side_bearing(4) == -13


def test_pdfbox_camelcase_accessors_delegate_to_snake_case() -> None:
    blob = b"".join([
        _pack_metric(1000, 80),
        _pack_metric(900, -10),
        _pack_tsb(11),
    ])
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(_StubTTF(num_glyphs=3, v_header=_StubVHEA(num_v_metrics=2)),
              MemoryTTFDataStream(blob))

    assert table.getAdvanceHeight(0) == table.get_advance_height(0)
    assert table.getAdvanceHeight(2) == table.get_advance_height(2)
    assert table.getTopSideBearing(0) == table.get_top_side_bearing(0)
    assert table.getTopSideBearing(2) == table.get_top_side_bearing(2)


def test_read_raises_when_no_vertical_header() -> None:
    table = VerticalMetricsTable()
    table.set_length(0)
    with pytest.raises(OSError, match="Could not get vhea table"):
        table.read(_StubTTF(num_glyphs=1, v_header=None),
                   MemoryTTFDataStream(b""))


def test_read_handles_bad_font_too_many_v_metrics() -> None:
    # numVMetrics > numGlyphs — should not crash. The trailing-TSB block
    # is only allocated when bytes remain in the table; with all bytes
    # consumed by the metrics, no additional TSB array is created.
    blob = _pack_metric(1000, 80) + _pack_metric(900, -10)
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(_StubTTF(num_glyphs=1, v_header=_StubVHEA(num_v_metrics=2)),
              MemoryTTFDataStream(blob))
    assert table.get_advance_height(0) == 1000
    # gid==5 falls back to the last advance entry
    assert table.get_advance_height(5) == 900


def test_get_advance_height_falls_back_to_last() -> None:
    # 1 vMetric covers a 4-glyph monospaced-style font; no trailing TSBs
    # supplied (length cap stops further reads).
    blob = _pack_metric(1000, 80)
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(_StubTTF(num_glyphs=4, v_header=_StubVHEA(num_v_metrics=1)),
              MemoryTTFDataStream(blob))
    assert table.get_advance_height(0) == 1000
    # With only 1 vMetric and no extra TSBs, every higher gid reuses the
    # last advance and there is no additional-TSB lookup invoked
    # (that path would IndexError — exactly mirroring upstream).
    assert table.get_advance_height(3) == 1000


def test_signed_tsb_two_complement() -> None:
    blob = _pack_metric(1000, -32768) + _pack_metric(1000, 32767)
    table = VerticalMetricsTable()
    table.set_length(len(blob))
    table.read(_StubTTF(num_glyphs=2, v_header=_StubVHEA(num_v_metrics=2)),
              MemoryTTFDataStream(blob))
    assert table.get_top_side_bearing(0) == -32768
    assert table.get_top_side_bearing(1) == 32767


def test_tag_constant() -> None:
    assert VerticalMetricsTable.TAG == "vmtx"


# ---------- TrueTypeFont.get_vertical_metrics() integration --------------


def _synthesize_font_with_vmtx(advance: int = 1000) -> bytes:
    """Patch a vhea + vmtx onto LiberationSans (which lacks them) and
    re-serialize via fontTools. Returns the raw TTF bytes.
    """
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    from fontTools.ttLib import TTFont, newTable  # noqa: PLC0415

    font = TTFont(io.BytesIO(FIXTURE.read_bytes()))
    vhea = newTable("vhea")
    vhea.tableVersion = 0x00010000
    vhea.ascent = 880
    vhea.descent = -120
    vhea.lineGap = 200
    vhea.advanceHeightMax = advance
    vhea.minTopSideBearing = -50
    vhea.minBottomSideBearing = -10
    vhea.yMaxExtent = 900
    vhea.caretSlopeRise = 0
    vhea.caretSlopeRun = 1
    vhea.caretOffset = 0
    vhea.reserved1 = 0
    vhea.reserved2 = 0
    vhea.reserved3 = 0
    vhea.reserved4 = 0
    vhea.metricDataFormat = 0
    vhea.numberOfVMetrics = 0  # recomputed on save
    font["vhea"] = vhea

    vmtx = newTable("vmtx")
    # Vary TSB so the per-glyph map is non-trivial; keep advance constant
    # so most glyphs end up sharing the trailing TSB-only block on disk.
    vmtx.metrics = {
        name: (advance, (i % 11) * 3 - 5)
        for i, name in enumerate(font.getGlyphOrder())
    }
    font["vmtx"] = vmtx

    font.recalcBBoxes = False
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def test_get_vertical_metrics_returns_none_when_absent() -> None:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    assert ttf.get_vertical_metrics() is None


def test_get_vertical_metrics_populated_from_fonttools() -> None:
    raw = _synthesize_font_with_vmtx(advance=1000)
    ttf = TrueTypeFont.from_bytes(raw)
    vmtx = ttf.get_vertical_metrics()
    assert vmtx is not None
    # Every glyph should report the constant advance height.
    n = ttf.get_number_of_glyphs()
    assert n > 1
    for gid in (0, 1, 2, n - 1):
        assert vmtx.get_advance_height(gid) == 1000
    # TSBs follow the (i % 11) * 3 - 5 schedule we set.
    expected_tsbs = [(i % 11) * 3 - 5 for i in range(n)]
    for gid in (0, 5, 10, n - 1):
        assert vmtx.get_top_side_bearing(gid) == expected_tsbs[gid]


def test_get_vertical_metrics_is_cached() -> None:
    raw = _synthesize_font_with_vmtx()
    ttf = TrueTypeFont.from_bytes(raw)
    a = ttf.get_vertical_metrics()
    b = ttf.get_vertical_metrics()
    assert a is b

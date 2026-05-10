from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.vertical_header_table import VerticalHeaderTable

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _build_vhea(
    *,
    version: tuple[int, int] = (1, 0),
    ascender: int = 880,
    descender: int = -120,
    line_gap: int = 200,
    advance_height_max: int = 1024,
    min_top_side_bearing: int = -50,
    min_bottom_side_bearing: int = -10,
    y_max_extent: int = 900,
    caret_slope_rise: int = 0,
    caret_slope_run: int = 1,
    caret_offset: int = 0,
    metric_data_format: int = 0,
    number_of_v_metrics: int = 256,
) -> bytes:
    return struct.pack(
        ">hHhhhHhhhhhhhhhhhH",
        version[0],
        version[1],
        ascender,
        descender,
        line_gap,
        advance_height_max,
        min_top_side_bearing,
        min_bottom_side_bearing,
        y_max_extent,
        caret_slope_rise,
        caret_slope_run,
        caret_offset,
        0,  # reserved1
        0,  # reserved2
        0,  # reserved3
        0,  # reserved4
        metric_data_format,
        number_of_v_metrics,
    )


def test_payload_is_exactly_36_bytes() -> None:
    assert len(_build_vhea()) == 36


def test_read_full_record() -> None:
    table = VerticalHeaderTable()
    table.read(None, MemoryTTFDataStream(_build_vhea()))  # type: ignore[arg-type]
    assert table.get_initialized() is True
    assert table.get_version() == 1.0
    assert table.get_ascender() == 880
    assert table.get_descender() == -120
    assert table.get_line_gap() == 200
    assert table.get_advance_height_max() == 1024
    assert table.get_min_top_side_bearing() == -50
    assert table.get_min_bottom_side_bearing() == -10
    assert table.get_y_max_extent() == 900
    assert table.get_caret_slope_rise() == 0
    assert table.get_caret_slope_run() == 1
    assert table.get_caret_offset() == 0
    assert table.get_metric_data_format() == 0
    assert table.get_number_of_v_metrics() == 256


def test_negative_signed_fields() -> None:
    raw = _build_vhea(
        ascender=-1,
        descender=-32768,
        line_gap=-1000,
        min_top_side_bearing=-32768,
        min_bottom_side_bearing=-32768,
        y_max_extent=-1,
        caret_slope_rise=-1,
        caret_slope_run=-1,
        caret_offset=-1,
        metric_data_format=-1,
    )
    table = VerticalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_ascender() == -1
    assert table.get_descender() == -32768
    assert table.get_line_gap() == -1000
    assert table.get_min_top_side_bearing() == -32768
    assert table.get_min_bottom_side_bearing() == -32768
    assert table.get_y_max_extent() == -1
    assert table.get_caret_slope_rise() == -1
    assert table.get_caret_slope_run() == -1
    assert table.get_caret_offset() == -1
    assert table.get_metric_data_format() == -1


def test_advance_height_max_is_unsigned() -> None:
    raw = _build_vhea(advance_height_max=0xFFFF)
    table = VerticalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_advance_height_max() == 65535


def test_number_of_v_metrics_is_unsigned() -> None:
    raw = _build_vhea(number_of_v_metrics=0xFFFF)
    table = VerticalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_number_of_v_metrics() == 65535


def test_tag_constant() -> None:
    assert VerticalHeaderTable.TAG == "vhea"


def test_defaults_before_read() -> None:
    table = VerticalHeaderTable()
    assert table.get_initialized() is False
    assert table.get_version() == 0.0
    assert table.get_ascender() == 0
    assert table.get_number_of_v_metrics() == 0
    assert table.get_caret_offset() == 0


def test_fractional_version_v1_1() -> None:
    # Version 1.1 — frac low byte 0x1000 -> 1 + 0x1000/0x10000 = 1.0625
    raw = _build_vhea(version=(1, 0x1000))
    table = VerticalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_version() == 1.0625


def test_reserved_fields_default_zero() -> None:
    table = VerticalHeaderTable()
    table.read(None, MemoryTTFDataStream(_build_vhea()))  # type: ignore[arg-type]
    assert table.get_reserved1() == 0
    assert table.get_reserved2() == 0
    assert table.get_reserved3() == 0
    assert table.get_reserved4() == 0


# ---------- TrueTypeFont.get_vertical_header() integration --------------


def _synthesize_font_with_vhea() -> bytes:
    """Patch a vhea + vmtx onto LiberationSans (which lacks them) and
    re-serialize via fontTools. Returns the raw TTF bytes.
    """
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    from fontTools.ttLib import TTFont, newTable  # noqa: PLC0415

    font = TTFont(io.BytesIO(FIXTURE.read_bytes()))
    vhea = newTable("vhea")
    vhea.tableVersion = 0x00011000  # 1.0625 — version 1.1
    vhea.ascent = 880
    vhea.descent = -120
    vhea.lineGap = 200
    vhea.advanceHeightMax = 1024
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
    vmtx.metrics = {
        name: (1000, (i % 7) * 5 - 10) for i, name in enumerate(font.getGlyphOrder())
    }
    font["vmtx"] = vmtx

    font.recalcBBoxes = False
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def test_get_vertical_header_returns_none_when_absent() -> None:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())
    # LiberationSans has no vhea — accessor must return None.
    assert ttf.get_vertical_header() is None


def test_get_vertical_header_populated_from_fonttools() -> None:
    raw = _synthesize_font_with_vhea()
    ttf = TrueTypeFont.from_bytes(raw)
    vhea = ttf.get_vertical_header()
    assert vhea is not None
    assert vhea.get_ascender() == 880
    assert vhea.get_descender() == -120
    assert vhea.get_line_gap() == 200
    # advanceHeightMax may be re-derived by fontTools' recalc — we
    # disabled recalcBBoxes so the value we set is preserved.
    assert vhea.get_advance_height_max() == 1024
    assert vhea.get_caret_slope_run() == 1
    assert vhea.get_caret_offset() == 0
    assert vhea.get_metric_data_format() == 0
    # Version is exposed as a 16.16 fixed-point float.
    assert vhea.get_version() == pytest.approx(1.0625, rel=1e-6)
    # numberOfVMetrics is recomputed by fontTools — ensure it is positive.
    assert vhea.get_number_of_v_metrics() > 0


def test_get_vertical_header_is_cached() -> None:
    raw = _synthesize_font_with_vhea()
    ttf = TrueTypeFont.from_bytes(raw)
    a = ttf.get_vertical_header()
    b = ttf.get_vertical_header()
    assert a is b

from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.horizontal_header_table import HorizontalHeaderTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _build_hhea(
    *,
    version: tuple[int, int] = (1, 0),
    ascender: int = 800,
    descender: int = -200,
    line_gap: int = 90,
    advance_width_max: int = 2048,
    min_left_side_bearing: int = -50,
    min_right_side_bearing: int = -10,
    x_max_extent: int = 1900,
    caret_slope_rise: int = 1,
    caret_slope_run: int = 0,
    reserved: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0),
    metric_data_format: int = 0,
    number_of_h_metrics: int = 256,
) -> bytes:
    return struct.pack(
        ">hHhhhHhhhhhhhhhhhH",
        version[0],
        version[1],
        ascender,
        descender,
        line_gap,
        advance_width_max,
        min_left_side_bearing,
        min_right_side_bearing,
        x_max_extent,
        caret_slope_rise,
        caret_slope_run,
        reserved[0],
        reserved[1],
        reserved[2],
        reserved[3],
        reserved[4],
        metric_data_format,
        number_of_h_metrics,
    )


def test_payload_is_exactly_36_bytes() -> None:
    assert len(_build_hhea()) == 36


def test_read_full_record() -> None:
    table = HorizontalHeaderTable()
    table.read(None, MemoryTTFDataStream(_build_hhea()))  # type: ignore[arg-type]
    assert table.get_initialized() is True
    assert table.get_version() == 1.0
    assert table.get_ascender() == 800
    assert table.get_descender() == -200
    assert table.get_line_gap() == 90
    assert table.get_advance_width_max() == 2048
    assert table.get_min_left_side_bearing() == -50
    assert table.get_min_right_side_bearing() == -10
    assert table.get_x_max_extent() == 1900
    assert table.get_caret_slope_rise() == 1
    assert table.get_caret_slope_run() == 0
    assert table.get_metric_data_format() == 0
    assert table.get_number_of_h_metrics() == 256


def test_negative_signed_fields() -> None:
    raw = _build_hhea(
        ascender=-1,
        descender=-32768,
        line_gap=-1000,
        min_left_side_bearing=-32768,
        min_right_side_bearing=-32768,
        x_max_extent=-1,
        caret_slope_rise=-1,
        caret_slope_run=-1,
        metric_data_format=-1,
    )
    table = HorizontalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_ascender() == -1
    assert table.get_descender() == -32768
    assert table.get_line_gap() == -1000
    assert table.get_min_left_side_bearing() == -32768
    assert table.get_min_right_side_bearing() == -32768
    assert table.get_x_max_extent() == -1
    assert table.get_caret_slope_rise() == -1
    assert table.get_caret_slope_run() == -1
    assert table.get_metric_data_format() == -1


def test_advance_width_max_is_unsigned() -> None:
    raw = _build_hhea(advance_width_max=0xFFFF)
    table = HorizontalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_advance_width_max() == 65535


def test_number_of_h_metrics_is_unsigned() -> None:
    raw = _build_hhea(number_of_h_metrics=0xFFFF)
    table = HorizontalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_number_of_h_metrics() == 65535


def test_tag_constant() -> None:
    assert HorizontalHeaderTable.TAG == "hhea"


def test_defaults_before_read() -> None:
    table = HorizontalHeaderTable()
    assert table.get_initialized() is False
    assert table.get_version() == 0.0
    assert table.get_ascender() == 0
    assert table.get_number_of_h_metrics() == 0


def test_fractional_version() -> None:
    raw = _build_hhea(version=(0, 0x8000))
    table = HorizontalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_version() == 0.5


def test_reserved_fields_are_preserved() -> None:
    raw = _build_hhea(reserved=(1, -2, 3, -4, 5))
    table = HorizontalHeaderTable()
    table.read(None, MemoryTTFDataStream(raw))  # type: ignore[arg-type]
    assert table.get_reserved1() == 1
    assert table.get_reserved2() == -2
    assert table.get_reserved3() == 3
    assert table.get_reserved4() == -4
    assert table.get_reserved5() == 5


def test_reserved_fields_default_zero() -> None:
    table = HorizontalHeaderTable()
    table.read(None, MemoryTTFDataStream(_build_hhea()))  # type: ignore[arg-type]
    assert table.get_reserved1() == 0
    assert table.get_reserved2() == 0
    assert table.get_reserved3() == 0
    assert table.get_reserved4() == 0
    assert table.get_reserved5() == 0


def test_set_number_of_h_metrics_round_trip() -> None:
    table = HorizontalHeaderTable()
    table.set_number_of_h_metrics(17)
    assert table.get_number_of_h_metrics() == 17

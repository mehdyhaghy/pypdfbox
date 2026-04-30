from __future__ import annotations

from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class HorizontalHeaderTable(TTFTable):
    """``hhea`` — required TrueType table. Mirrors upstream."""

    TAG: str = "hhea"

    def __init__(self) -> None:
        super().__init__()
        self._version: float = 0.0
        self._ascender: int = 0
        self._descender: int = 0
        self._line_gap: int = 0
        self._advance_width_max: int = 0
        self._min_left_side_bearing: int = 0
        self._min_right_side_bearing: int = 0
        self._x_max_extent: int = 0
        self._caret_slope_rise: int = 0
        self._caret_slope_run: int = 0
        self._reserved1: int = 0
        self._reserved2: int = 0
        self._reserved3: int = 0
        self._reserved4: int = 0
        self._reserved5: int = 0
        self._metric_data_format: int = 0
        self._number_of_h_metrics: int = 0

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        self._version = data.read_32_fixed()
        self._ascender = data.read_signed_short()
        self._descender = data.read_signed_short()
        self._line_gap = data.read_signed_short()
        self._advance_width_max = data.read_unsigned_short()
        self._min_left_side_bearing = data.read_signed_short()
        self._min_right_side_bearing = data.read_signed_short()
        self._x_max_extent = data.read_signed_short()
        self._caret_slope_rise = data.read_signed_short()
        self._caret_slope_run = data.read_signed_short()
        self._reserved1 = data.read_signed_short()
        self._reserved2 = data.read_signed_short()
        self._reserved3 = data.read_signed_short()
        self._reserved4 = data.read_signed_short()
        self._reserved5 = data.read_signed_short()
        self._metric_data_format = data.read_signed_short()
        self._number_of_h_metrics = data.read_unsigned_short()
        self.initialized = True

    # ---- accessors ----
    def get_version(self) -> float:
        return self._version

    def get_ascender(self) -> int:
        return self._ascender

    def get_descender(self) -> int:
        return self._descender

    def get_line_gap(self) -> int:
        return self._line_gap

    def get_advance_width_max(self) -> int:
        return self._advance_width_max

    def get_min_left_side_bearing(self) -> int:
        return self._min_left_side_bearing

    def get_min_right_side_bearing(self) -> int:
        return self._min_right_side_bearing

    def get_x_max_extent(self) -> int:
        return self._x_max_extent

    def get_caret_slope_rise(self) -> int:
        return self._caret_slope_rise

    def get_caret_slope_run(self) -> int:
        return self._caret_slope_run

    def get_reserved1(self) -> int:
        return self._reserved1

    def get_reserved2(self) -> int:
        return self._reserved2

    def get_reserved3(self) -> int:
        return self._reserved3

    def get_reserved4(self) -> int:
        return self._reserved4

    def get_reserved5(self) -> int:
        return self._reserved5

    def get_metric_data_format(self) -> int:
        return self._metric_data_format

    def get_number_of_h_metrics(self) -> int:
        return self._number_of_h_metrics

    def set_number_of_h_metrics(self, value: int) -> None:
        self._number_of_h_metrics = value

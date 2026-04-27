from __future__ import annotations

from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class VerticalHeaderTable(TTFTable):
    """``vhea`` — vertical header table for TrueType / OpenType fonts.

    Required by the OpenType CJK Font Guidelines for "all OpenType fonts
    that are used for vertical writing". Supports both version 1.0 and 1.1
    (1.1 only renames the ascender / descender / lineGap fields to
    vertTypoAscender / vertTypoDescender / vertTypoLineGap; the binary
    layout is identical).

    Mirrors :class:`org.apache.fontbox.ttf.VerticalHeaderTable`.
    """

    TAG: str = "vhea"

    def __init__(self) -> None:
        super().__init__()
        self._version: float = 0.0
        self._ascender: int = 0
        self._descender: int = 0
        self._line_gap: int = 0
        self._advance_height_max: int = 0
        self._min_top_side_bearing: int = 0
        self._min_bottom_side_bearing: int = 0
        self._y_max_extent: int = 0
        self._caret_slope_rise: int = 0
        self._caret_slope_run: int = 0
        self._caret_offset: int = 0
        self._reserved1: int = 0
        self._reserved2: int = 0
        self._reserved3: int = 0
        self._reserved4: int = 0
        self._metric_data_format: int = 0
        self._number_of_v_metrics: int = 0

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        self._version = data.read_32_fixed()
        self._ascender = data.read_signed_short()
        self._descender = data.read_signed_short()
        self._line_gap = data.read_signed_short()
        self._advance_height_max = data.read_unsigned_short()
        self._min_top_side_bearing = data.read_signed_short()
        self._min_bottom_side_bearing = data.read_signed_short()
        self._y_max_extent = data.read_signed_short()
        self._caret_slope_rise = data.read_signed_short()
        self._caret_slope_run = data.read_signed_short()
        self._caret_offset = data.read_signed_short()
        self._reserved1 = data.read_signed_short()
        self._reserved2 = data.read_signed_short()
        self._reserved3 = data.read_signed_short()
        self._reserved4 = data.read_signed_short()
        self._metric_data_format = data.read_signed_short()
        self._number_of_v_metrics = data.read_unsigned_short()
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

    def get_advance_height_max(self) -> int:
        return self._advance_height_max

    def get_min_top_side_bearing(self) -> int:
        return self._min_top_side_bearing

    def get_min_bottom_side_bearing(self) -> int:
        return self._min_bottom_side_bearing

    def get_y_max_extent(self) -> int:
        return self._y_max_extent

    def get_caret_slope_rise(self) -> int:
        return self._caret_slope_rise

    def get_caret_slope_run(self) -> int:
        return self._caret_slope_run

    def get_caret_offset(self) -> int:
        return self._caret_offset

    def get_reserved1(self) -> int:
        return self._reserved1

    def get_reserved2(self) -> int:
        return self._reserved2

    def get_reserved3(self) -> int:
        return self._reserved3

    def get_reserved4(self) -> int:
        return self._reserved4

    def get_metric_data_format(self) -> int:
        return self._metric_data_format

    def get_number_of_v_metrics(self) -> int:
        return self._number_of_v_metrics


__all__ = ["VerticalHeaderTable"]

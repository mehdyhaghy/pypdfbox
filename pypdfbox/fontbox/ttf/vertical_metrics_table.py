from __future__ import annotations

from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class VerticalMetricsTable(TTFTable):
    """``vmtx`` — per-glyph advance height and top-side bearing.

    Mirrors :class:`org.apache.fontbox.ttf.VerticalMetricsTable`, including
    the upstream hardening for bad fonts (``numberOfVMetrics > numGlyphs``
    and missing trailing top-side-bearing array).
    """

    TAG: str = "vmtx"

    def __init__(self) -> None:
        super().__init__()
        self._advance_height: list[int] = []
        self._top_side_bearing: list[int] = []
        self._additional_top_side_bearing: list[int] = []
        self._num_v_metrics: int = 0

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        v_header = ttf.get_vertical_header()
        if v_header is None:
            raise OSError("Could not get vhea table")
        self._num_v_metrics = v_header.get_number_of_v_metrics()
        num_glyphs = ttf.get_number_of_glyphs()

        bytes_read = 0
        self._advance_height = [0] * self._num_v_metrics
        self._top_side_bearing = [0] * self._num_v_metrics
        for i in range(self._num_v_metrics):
            self._advance_height[i] = data.read_unsigned_short()
            self._top_side_bearing[i] = data.read_signed_short()
            bytes_read += 4

        if bytes_read < self.get_length():
            number_non_vertical = num_glyphs - self._num_v_metrics
            # handle bad fonts with too many vmetrics
            if number_non_vertical < 0:
                number_non_vertical = num_glyphs

            self._additional_top_side_bearing = [0] * number_non_vertical
            for i in range(number_non_vertical):
                if bytes_read < self.get_length():
                    self._additional_top_side_bearing[i] = data.read_signed_short()
                    bytes_read += 2

        self.initialized = True

    def get_advance_height(self, gid: int) -> int:
        if gid < self._num_v_metrics:
            return self._advance_height[gid]
        # monospaced fonts may not have a height for every glyph;
        # fall back to the last entry.
        return self._advance_height[-1]

    def get_top_side_bearing(self, gid: int) -> int:
        if gid < self._num_v_metrics:
            return self._top_side_bearing[gid]
        return self._additional_top_side_bearing[gid - self._num_v_metrics]


__all__ = ["VerticalMetricsTable"]

from __future__ import annotations

from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class HorizontalMetricsTable(TTFTable):
    """``hmtx`` — required TrueType table. Per-glyph advance width and
    left-side bearing. Mirrors upstream behavior including the bad-font
    hardening (``numHMetrics > numGlyphs`` and missing trailing LSBs).
    """

    TAG: str = "hmtx"

    def __init__(self) -> None:
        super().__init__()
        self._advance_width: list[int] = []
        self._left_side_bearing: list[int] = []
        self._non_horizontal_left_side_bearing: list[int] = []
        self._num_h_metrics: int = 0

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        h_header = ttf.get_horizontal_header()
        if h_header is None:
            raise OSError("Could not get hmtx table")
        self._num_h_metrics = h_header.get_number_of_h_metrics()
        num_glyphs = ttf.get_number_of_glyphs()

        bytes_read = 0
        self._advance_width = [0] * self._num_h_metrics
        self._left_side_bearing = [0] * self._num_h_metrics
        for i in range(self._num_h_metrics):
            self._advance_width[i] = data.read_unsigned_short()
            self._left_side_bearing[i] = data.read_signed_short()
            bytes_read += 4

        number_non_horizontal = num_glyphs - self._num_h_metrics
        # handle bad fonts with too many hmetrics
        if number_non_horizontal < 0:
            number_non_horizontal = num_glyphs

        # Always allocate (even with bad fonts that lack a trailing LSB array).
        self._non_horizontal_left_side_bearing = [0] * number_non_horizontal

        if bytes_read < self.get_length():
            for i in range(number_non_horizontal):
                if bytes_read < self.get_length():
                    self._non_horizontal_left_side_bearing[i] = data.read_signed_short()
                    bytes_read += 2

        self.initialized = True

    def get_advance_width(self, gid: int) -> int:
        if not self._advance_width:
            return 250
        if gid < self._num_h_metrics:
            # Upstream indexes ``advanceWidth[gid]`` directly; a negative gid
            # throws ArrayIndexOutOfBounds in Java. Python negative-indexing
            # would silently wrap to the last entry, so guard to preserve the
            # upstream throw semantics rather than diverge.
            if gid < 0:
                raise IndexError(f"advance width index out of range: {gid}")
            return self._advance_width[gid]
        # monospaced fonts may not have a width for every glyph; fall back to last entry.
        return self._advance_width[-1]

    def get_left_side_bearing(self, gid: int) -> int:
        if not self._left_side_bearing:
            return 0
        if gid < self._num_h_metrics:
            if gid < 0:
                raise IndexError(f"left side bearing index out of range: {gid}")
            return self._left_side_bearing[gid]
        # gid >= numHMetrics: upstream indexes the trailing LSB-only array with
        # no bounds check, so an out-of-range gid throws (we let IndexError
        # propagate, mirroring the Java ArrayIndexOutOfBounds).
        return self._non_horizontal_left_side_bearing[gid - self._num_h_metrics]

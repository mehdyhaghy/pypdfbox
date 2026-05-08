from __future__ import annotations

from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class IndexToLocationTable(TTFTable):
    """``loca`` — required TrueType table. Mirrors upstream."""

    TAG: str = "loca"
    _SHORT_OFFSETS: int = 0
    _LONG_OFFSETS: int = 1

    def __init__(self) -> None:
        super().__init__()
        self._offsets: list[int] = []

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        head = ttf.get_header()
        if head is None:
            raise OSError("Could not get head table")
        num_glyphs = ttf.get_number_of_glyphs()
        self._offsets = [0] * (num_glyphs + 1)
        fmt = head.get_index_to_loc_format()
        for i in range(num_glyphs + 1):
            if fmt == self._SHORT_OFFSETS:
                self._offsets[i] = data.read_unsigned_short() * 2
            elif fmt == self._LONG_OFFSETS:
                self._offsets[i] = data.read_unsigned_int()
            else:
                raise OSError(f"Error:TTF.loca unknown offset format: {fmt}")

        for previous, current in zip(self._offsets, self._offsets[1:], strict=False):
            if current < previous:
                raise OSError("The loca table contains decreasing offsets")

        if num_glyphs == 1 and self._offsets[0] == 0 and self._offsets[1] == 0:
            # PDFBOX-5794 empty glyph
            raise OSError("The font has no glyphs")

        self.initialized = True

    def get_offsets(self) -> list[int]:
        return self._offsets

    def set_offsets(self, value: list[int]) -> None:
        self._offsets = value

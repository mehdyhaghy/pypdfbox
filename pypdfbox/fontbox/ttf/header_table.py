from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class HeaderTable(TTFTable):
    """``head`` — required TrueType table.

    Mirrors ``org.apache.fontbox.ttf.HeaderTable``.
    """

    TAG: str = "head"
    MAC_STYLE_BOLD: int = 1
    MAC_STYLE_ITALIC: int = 2

    def __init__(self) -> None:
        super().__init__()
        self._version: float = 0.0
        self._font_revision: float = 0.0
        self._check_sum_adjustment: int = 0
        self._magic_number: int = 0
        self._flags: int = 0
        self._units_per_em: int = 0
        self._created: datetime | None = None
        self._modified: datetime | None = None
        self._x_min: int = 0
        self._y_min: int = 0
        self._x_max: int = 0
        self._y_max: int = 0
        self._mac_style: int = 0
        self._lowest_rec_ppem: int = 0
        self._font_direction_hint: int = 0
        self._index_to_loc_format: int = 0
        self._glyph_data_format: int = 0

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        self._version = data.read_32_fixed()
        self._font_revision = data.read_32_fixed()
        self._check_sum_adjustment = data.read_unsigned_int()
        self._magic_number = data.read_unsigned_int()
        self._flags = data.read_unsigned_short()
        self._units_per_em = data.read_unsigned_short()
        self._created = data.read_long_date_time()
        self._modified = data.read_long_date_time()
        self._x_min = data.read_signed_short()
        self._y_min = data.read_signed_short()
        self._x_max = data.read_signed_short()
        self._y_max = data.read_signed_short()
        self._mac_style = data.read_unsigned_short()
        self._lowest_rec_ppem = data.read_unsigned_short()
        self._font_direction_hint = data.read_signed_short()
        self._index_to_loc_format = data.read_signed_short()
        self._glyph_data_format = data.read_signed_short()
        self.initialized = True

    # ---- accessors ----
    def get_version(self) -> float:
        return self._version

    def get_font_revision(self) -> float:
        return self._font_revision

    def get_check_sum_adjustment(self) -> int:
        return self._check_sum_adjustment

    def get_magic_number(self) -> int:
        return self._magic_number

    def get_flags(self) -> int:
        return self._flags

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def get_created(self) -> datetime | None:
        return self._created

    def get_modified(self) -> datetime | None:
        return self._modified

    def get_x_min(self) -> int:
        return self._x_min

    def get_y_min(self) -> int:
        return self._y_min

    def get_x_max(self) -> int:
        return self._x_max

    def get_y_max(self) -> int:
        return self._y_max

    def get_mac_style(self) -> int:
        return self._mac_style

    def get_lowest_rec_ppem(self) -> int:
        return self._lowest_rec_ppem

    def get_font_direction_hint(self) -> int:
        return self._font_direction_hint

    def get_index_to_loc_format(self) -> int:
        return self._index_to_loc_format

    def get_glyph_data_format(self) -> int:
        return self._glyph_data_format

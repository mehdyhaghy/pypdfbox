from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream
    from .ttf_parser import FontHeaders


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

    def read_headers(
        self,
        ttf: TrueTypeFont,  # noqa: ARG002
        data: TTFDataStream,
        out_headers: FontHeaders,
    ) -> None:
        """Fast-path header read for ``FileSystemFontProvider``.

        Mirrors upstream ``HeaderTable.readHeaders`` (HeaderTable.java
        L69-L75): seek 44 bytes past the current position to skip the
        version / fontRevision / checksum / magic / flags / unitsPerEm /
        created / modified / xMin / yMin / xMax / yMax fields, then read
        ``macStyle`` (an unsigned short) and forward it to
        ``out_headers.set_header_mac_style(...)``. The class field
        ``_mac_style`` is also populated as a side-effect — same as
        upstream — so a follow-up :meth:`get_mac_style` call returns the
        right value without re-reading.
        """
        # 44 == 4 + 4 + 4 + 4 + 2 + 2 + 2*8 + 4*2, matching the field
        # layout in :meth:`read` above.
        data.seek(data.get_current_position() + 44)
        self._mac_style = data.read_unsigned_short()
        out_headers.set_header_mac_style(self._mac_style)

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

    def set_version(self, value: float) -> None:
        self._version = value

    def get_font_revision(self) -> float:
        return self._font_revision

    def set_font_revision(self, value: float) -> None:
        self._font_revision = value

    def get_check_sum_adjustment(self) -> int:
        return self._check_sum_adjustment

    def set_check_sum_adjustment(self, value: int) -> None:
        self._check_sum_adjustment = value

    def get_magic_number(self) -> int:
        return self._magic_number

    def set_magic_number(self, value: int) -> None:
        self._magic_number = value

    def get_flags(self) -> int:
        return self._flags

    def set_flags(self, value: int) -> None:
        self._flags = value

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def set_units_per_em(self, value: int) -> None:
        self._units_per_em = value

    def get_created(self) -> datetime | None:
        return self._created

    def set_created(self, value: datetime | None) -> None:
        self._created = value

    def get_modified(self) -> datetime | None:
        return self._modified

    def set_modified(self, value: datetime | None) -> None:
        self._modified = value

    def get_x_min(self) -> int:
        return self._x_min

    def set_x_min(self, value: int) -> None:
        self._x_min = value

    def get_y_min(self) -> int:
        return self._y_min

    def set_y_min(self, value: int) -> None:
        self._y_min = value

    def get_x_max(self) -> int:
        return self._x_max

    def set_x_max(self, value: int) -> None:
        self._x_max = value

    def get_y_max(self) -> int:
        return self._y_max

    def set_y_max(self, value: int) -> None:
        self._y_max = value

    def get_mac_style(self) -> int:
        return self._mac_style

    def set_mac_style(self, value: int) -> None:
        self._mac_style = value

    def get_lowest_rec_ppem(self) -> int:
        return self._lowest_rec_ppem

    def set_lowest_rec_ppem(self, value: int) -> None:
        self._lowest_rec_ppem = value

    def get_font_direction_hint(self) -> int:
        return self._font_direction_hint

    def set_font_direction_hint(self, value: int) -> None:
        self._font_direction_hint = value

    def get_index_to_loc_format(self) -> int:
        return self._index_to_loc_format

    def set_index_to_loc_format(self, value: int) -> None:
        self._index_to_loc_format = value

    def get_glyph_data_format(self) -> int:
        return self._glyph_data_format

    def set_glyph_data_format(self, value: int) -> None:
        self._glyph_data_format = value

    # ---- predicate helpers (no upstream equivalent — additions) ----

    def is_bold(self) -> bool:
        """``True`` if the macStyle Bold bit (0x01) is set.

        Mirrors the test upstream callers (e.g. ``PDTrueTypeFont`` / font
        mapper) perform inline as ``getMacStyle() & MAC_STYLE_BOLD``.
        """
        return bool(self._mac_style & self.MAC_STYLE_BOLD)

    def is_italic(self) -> bool:
        """``True`` if the macStyle Italic bit (0x02) is set."""
        return bool(self._mac_style & self.MAC_STYLE_ITALIC)

    def get_bbox(self) -> tuple[int, int, int, int]:
        """Glyph-data bounding box as ``(x_min, y_min, x_max, y_max)``.

        Convenience tuple for callers that want to forward the head-table
        bbox to a font descriptor without unpacking four accessors.
        """
        return (self._x_min, self._y_min, self._x_max, self._y_max)

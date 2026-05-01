from __future__ import annotations

from typing import TYPE_CHECKING

from .cmap_subtable import CmapSubtable
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class CmapTable(TTFTable):
    """``cmap`` — required TrueType table.

    Mirrors ``org.apache.fontbox.ttf.CmapTable``. The class exposes the
    parsed :class:`CmapSubtable` array along with the platform / encoding
    constants that callers use when picking a specific subtable.
    """

    # Tag identifying this table.
    TAG: str = "cmap"

    # Platform IDs.
    PLATFORM_UNICODE: int = 0
    PLATFORM_MACINTOSH: int = 1
    PLATFORM_WINDOWS: int = 3

    # Macintosh encodings.
    ENCODING_MAC_ROMAN: int = 0

    # Windows encodings.
    ENCODING_WIN_SYMBOL: int = 0  # Unicode, non-standard character set
    ENCODING_WIN_UNICODE_BMP: int = 1  # Unicode BMP (UCS-2)
    ENCODING_WIN_SHIFT_JIS: int = 2
    ENCODING_WIN_BIG5: int = 3
    ENCODING_WIN_PRC: int = 4
    ENCODING_WIN_WANSUNG: int = 5
    ENCODING_WIN_JOHAB: int = 6
    ENCODING_WIN_UNICODE_FULL: int = 10  # Unicode Full (UCS-4)

    # Unicode encodings.
    ENCODING_UNICODE_1_0: int = 0
    ENCODING_UNICODE_1_1: int = 1
    ENCODING_UNICODE_2_0_BMP: int = 3
    ENCODING_UNICODE_2_0_FULL: int = 4

    def __init__(self) -> None:
        super().__init__()
        self._cmaps: list[CmapSubtable] = []

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        """Read the ``cmap`` directory and all its subtables.

        Mirrors upstream's ``read(TrueTypeFont, TTFDataStream)``:
        consumes the table-version word, the subtable count, and then a
        directory entry per subtable, before walking the entries a second
        time to populate them with per-format data.
        """
        # version word — read but ignored, exactly as upstream does.
        data.read_unsigned_short()
        number_of_tables = data.read_unsigned_short()
        cmaps: list[CmapSubtable] = []
        for _ in range(number_of_tables):
            sub = CmapSubtable()
            sub.init_data(data)
            cmaps.append(sub)
        number_of_glyphs = ttf.get_number_of_glyphs()
        for sub in cmaps:
            sub.init_subtable(self, number_of_glyphs, data)
        self._cmaps = cmaps
        self.initialized = True

    # ---- accessors ----

    def get_cmaps(self) -> list[CmapSubtable]:
        """Return the parsed cmap subtables in directory order.

        Upstream returns ``CmapSubtable[]`` (Java array); we return a
        Python ``list`` containing the same elements. The list is the
        live storage — mutating it mutates the table, matching upstream
        array-aliasing semantics.
        """
        return self._cmaps

    def set_cmaps(self, value: list[CmapSubtable]) -> None:
        """Replace the cmap subtable list."""
        self._cmaps = value

    def get_subtable(
        self, platform_id: int, platform_encoding_id: int
    ) -> CmapSubtable | None:
        """Return the first subtable matching ``(platform_id, platform_encoding_id)``.

        Returns ``None`` if no such subtable exists, mirroring upstream
        which returns ``null`` in the same case.
        """
        for sub in self._cmaps:
            if (
                sub.get_platform_id() == platform_id
                and sub.get_platform_encoding_id() == platform_encoding_id
            ):
                return sub
        return None

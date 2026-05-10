"""Vertical Origin ``VORG`` table.

Mirrors ``org.apache.fontbox.ttf.VerticalOriginTable`` (upstream
``VerticalOriginTable.java`` L38-96). Used by CFF OpenType fonts in
vertical writing modes so a renderer can read the glyph's vertical
origin Y directly instead of computing it from the CFF bounding box.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class VerticalOriginTable(TTFTable):
    """The ``VORG`` SFNT table.

    Mirrors ``VerticalOriginTable.java`` L38-96. On-disk layout:

    * ``version`` (Fixed32, major.minor with the upstream ``read32Fixed``
      decoding — a 32-bit fixed-point value with the integer part in
      the high 16 bits).
    * ``defaultVertOriginY`` (int16) — y-origin used when a glyph isn't
      listed in the per-glyph table.
    * ``numVertOriginYMetrics`` (uint16) — number of (gid, originY)
      entries that follow.
    * ``numVertOriginYMetrics`` * (gid uint16, originY int16) records.
    """

    #: Tag that identifies this table type. Mirrors
    #: ``VerticalOriginTable.TAG`` (upstream L43).
    TAG: str = "VORG"

    def __init__(self) -> None:
        super().__init__()
        self._version: float = 0.0
        self._default_vert_origin_y: int = 0
        self._origins: dict[int, int] = {}

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:  # noqa: ARG002
        """Mirror ``read(TrueTypeFont, TTFDataStream)``
        (VerticalOriginTable.java L62-75)."""
        self._version = data.read_32_fixed()
        self._default_vert_origin_y = data.read_signed_short()
        num_vert_origin_y_metrics = data.read_unsigned_short()
        origins: dict[int, int] = {}
        for _ in range(num_vert_origin_y_metrics):
            g = data.read_unsigned_short()
            y = data.read_signed_short()
            origins[g] = y
        self._origins = origins
        self.initialized = True

    def get_version(self) -> float:
        """Mirror ``getVersion()`` (VerticalOriginTable.java L80-83)."""
        return self._version

    def get_origin_y(self, gid: int) -> int:
        """Mirror ``getOriginY(int)`` (VerticalOriginTable.java L92-95).

        Returns the explicit vertical origin Y for ``gid`` when listed,
        otherwise the table's default.
        """
        return self._origins.get(gid, self._default_vert_origin_y)


__all__ = ["VerticalOriginTable"]

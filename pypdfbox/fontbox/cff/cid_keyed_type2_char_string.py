"""CID-keyed Type 2 char string.

Mirrors upstream ``org.apache.fontbox.cff.CIDKeyedType2CharString``
(CIDKeyedType2CharString.java:29). Subclass of ``Type2CharString`` that
carries the CID associated with the glyph in addition to the GID.
"""

from __future__ import annotations

from typing import Any

from .type2_char_string import Type2CharString


class CIDKeyedType2CharString(Type2CharString):
    """Mirrors upstream ``CIDKeyedType2CharString``
    (CIDKeyedType2CharString.java:29). Glyph name is synthesised as
    ``"%04x"`` of the CID, matching upstream
    (CIDKeyedType2CharString.java:47)."""

    def __init__(
        self,
        font: Any,
        font_name: str,
        cid: int,
        gid: int,
        sequence: Any,
        default_width_x: int = 0,
        nominal_width_x: int = 0,
    ) -> None:
        # Upstream signature (CIDKeyedType2CharString.java:44):
        #   CIDKeyedType2CharString(Type1CharStringReader font,
        #     String fontName, int cid, int gid, List<Object> sequence,
        #     int defaultWidthX, int nomWidthX)
        glyph_name = f"{int(cid):04x}"
        super().__init__(
            font=font,
            font_name=font_name,
            glyph_name=glyph_name,
            gid=gid,
            sequence=sequence,
            default_width_x=default_width_x,
            nominal_width_x=nominal_width_x,
        )
        self._cid = int(cid)

    def get_cid(self) -> int:
        """Mirrors upstream ``getCID``
        (CIDKeyedType2CharString.java:56)."""
        return self._cid


__all__ = ["CIDKeyedType2CharString"]

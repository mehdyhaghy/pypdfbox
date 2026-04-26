from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font


class PDCIDFontType2(PDCIDFont):
    """CIDFontType2 — TrueType-based CIDFont. Mirrors PDFBox ``PDCIDFontType2``.

    Lite — wraps the dictionary surface only; TrueType program parsing,
    CIDToGIDMap stream interpretation, and per-glyph metrics are deferred
    to the fontbox cluster.
    """

    SUB_TYPE = "CIDFontType2"

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        parent_type0_font: PDType0Font | None = None,
    ) -> None:
        super().__init__(font_dict, parent_type0_font)

    def get_subtype(self) -> str | None:
        return self.SUB_TYPE


__all__ = ["PDCIDFontType2"]

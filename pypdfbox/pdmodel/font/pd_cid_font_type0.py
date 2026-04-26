from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font


class PDCIDFontType0(PDCIDFont):
    """CIDFontType0 — CFF-based CIDFont. Mirrors PDFBox ``PDCIDFontType0``.

    Lite — wraps the dictionary surface only; CFF parsing / glyph metric
    extraction is deferred to the fontbox cluster.
    """

    SUB_TYPE = "CIDFontType0"

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        parent_type0_font: PDType0Font | None = None,
    ) -> None:
        super().__init__(font_dict, parent_type0_font)

    def get_subtype(self) -> str | None:
        return self.SUB_TYPE


__all__ = ["PDCIDFontType0"]

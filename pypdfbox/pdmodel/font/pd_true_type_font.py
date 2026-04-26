from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_simple_font import PDSimpleFont


class PDTrueTypeFont(PDSimpleFont):
    """PDF TrueType font. Mirrors PDFBox ``PDTrueTypeFont``."""

    SUB_TYPE = "TrueType"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)


__all__ = ["PDTrueTypeFont"]

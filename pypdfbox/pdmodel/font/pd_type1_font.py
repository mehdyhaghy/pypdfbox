from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_simple_font import PDSimpleFont


class PDType1Font(PDSimpleFont):
    """PDF Type 1 (PostScript) font. Mirrors PDFBox ``PDType1Font``."""

    SUB_TYPE = "Type1"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)


__all__ = ["PDType1Font"]

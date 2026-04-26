from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_font import PDFont
from .pd_true_type_font import PDTrueTypeFont
from .pd_type0_font import PDType0Font
from .pd_type1_font import PDType1Font

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]


class PDFontFactory:
    """Static dispatch from a font ``COSDictionary`` to the right
    ``PDFont`` subclass, keyed on ``/Subtype``. Mirrors PDFBox
    ``PDFontFactory.createFont(COSDictionary)``.

    Lite — only ``Type1``, ``TrueType``, and ``Type0`` are wired. Other
    upstream subtypes (``Type3``, ``MMType1``, ``CIDFontType0``,
    ``CIDFontType2``) return ``None`` because their typed wrappers are
    not yet ported.
    """

    @staticmethod
    def create_font(font_dict: COSDictionary) -> PDFont | None:
        if font_dict is None:
            return None
        if not isinstance(font_dict, COSDictionary):
            raise TypeError(
                f"PDFontFactory.create_font expects COSDictionary, "
                f"got {type(font_dict).__name__}"
            )
        sub_type = font_dict.get_name(_SUBTYPE)
        if sub_type == PDType1Font.SUB_TYPE:
            return PDType1Font(font_dict)
        if sub_type == PDTrueTypeFont.SUB_TYPE:
            return PDTrueTypeFont(font_dict)
        if sub_type == PDType0Font.SUB_TYPE:
            return PDType0Font(font_dict)
        # Type3, MMType1, CIDFontType0, CIDFontType2 — wrappers deferred.
        return None


__all__ = ["PDFontFactory"]

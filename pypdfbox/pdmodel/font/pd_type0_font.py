from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_font import PDFont

_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")


class PDType0Font(PDFont):
    """PDF Type 0 (composite) font. Mirrors PDFBox ``PDType0Font``.

    A composite font references exactly one descendant CIDFont via the
    ``/DescendantFonts`` array. The typed ``PDCIDFont`` wrapper hierarchy
    is not yet ported, so ``get_descendant_font`` returns the raw
    ``COSDictionary`` of the first descendant.
    """

    SUB_TYPE = "Type0"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)

    def get_descendant_font(self) -> "PDCIDFont | None":
        """Return the typed ``PDCIDFont`` wrapper for the first
        ``/DescendantFonts`` entry, or ``None`` when absent / malformed.
        """
        arr = self._dict.get_dictionary_object(_DESCENDANT_FONTS)
        if not isinstance(arr, COSArray) or arr.size() == 0:
            return None
        first = arr.get_object(0)
        if isinstance(first, COSDictionary):
            return PDType0Font._wrap_descendant(first, self)
        return None

    @staticmethod
    def _wrap_descendant(
        font_dict: COSDictionary, parent: "PDType0Font"
    ) -> "PDCIDFont | None":
        from .pd_cid_font_type0 import PDCIDFontType0
        from .pd_cid_font_type2 import PDCIDFontType2

        sub_type = font_dict.get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        if sub_type == PDCIDFontType0.SUB_TYPE:
            return PDCIDFontType0(font_dict, parent)
        if sub_type == PDCIDFontType2.SUB_TYPE:
            return PDCIDFontType2(font_dict, parent)
        return None


__all__ = ["PDType0Font"]

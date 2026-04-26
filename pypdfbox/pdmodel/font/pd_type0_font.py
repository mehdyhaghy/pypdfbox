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

    def get_descendant_font(self) -> COSDictionary | None:
        """Return the raw ``COSDictionary`` of the first ``/DescendantFonts``
        entry, or ``None`` when absent / malformed.

        Lite — typed ``PDCIDFont`` wrappers are deferred.
        """
        arr = self._dict.get_dictionary_object(_DESCENDANT_FONTS)
        if not isinstance(arr, COSArray) or arr.size() == 0:
            return None
        first = arr.get_object(0)
        if isinstance(first, COSDictionary):
            return first
        return None


__all__ = ["PDType0Font"]

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_annotation_markup import PDAnnotationMarkup

_INK_LIST: COSName = COSName.get_pdf_name("InkList")


class PDAnnotationInk(PDAnnotationMarkup):
    """``/Subtype /Ink`` annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationInk``.

    ``/InkList`` is an array of arrays — each inner array is a stroked
    path of alternating x/y float coordinates (PDF 32000-1:2008 §12.5.6.13).
    """

    SUB_TYPE: str = "Ink"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /InkList ----------

    def get_ink_list(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_INK_LIST)
        if isinstance(value, COSArray):
            return value
        return None

    def set_ink_list(self, arr: COSArray | None) -> None:
        if arr is None:
            self._dict.remove_item(_INK_LIST)
            return
        self._dict.set_item(_INK_LIST, arr)


__all__ = ["PDAnnotationInk"]

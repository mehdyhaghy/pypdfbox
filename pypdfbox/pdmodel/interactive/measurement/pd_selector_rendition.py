from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_rendition import PDRendition

_S: COSName = COSName.get_pdf_name("S")
_R: COSName = COSName.get_pdf_name("R")


class PDSelectorRendition(PDRendition):
    """Rendition of subtype ``/SR`` (selector rendition).

    Mirrors PDFBox ``PDSelectorRendition``. ``/R`` is an array of
    sub-renditions, the first playable of which the viewer should use."""

    SUB_TYPE = "SR"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self._dict.set_name(_S, self.SUB_TYPE)

    def get_r(self) -> list[PDRendition]:
        arr = self._dict.get_dictionary_object(_R)
        if not isinstance(arr, COSArray):
            return []
        out: list[PDRendition] = []
        for i in range(arr.size()):
            entry = arr.get_object(i)
            if isinstance(entry, COSDictionary):
                rendition = PDRendition.create(entry)
                if rendition is not None:
                    out.append(rendition)
        return out

    def set_r(self, renditions: list[PDRendition] | None) -> None:
        if renditions is None:
            self._dict.remove_item(_R)
            return
        arr = COSArray()
        for r in renditions:
            arr.add(r.get_cos_object())
        self._dict.set_item(_R, arr)


__all__ = ["PDSelectorRendition"]

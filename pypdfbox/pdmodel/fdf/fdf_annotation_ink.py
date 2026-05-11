from __future__ import annotations

from collections.abc import Iterable

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .fdf_annotation import FDFAnnotation

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_INKLIST: COSName = COSName.get_pdf_name("InkList")


class FDFAnnotationInk(FDFAnnotation):
    """FDF Ink annotation — ``/Subtype /Ink``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationInk`` (Java
    lines 43-154). The ink annotation is made up of one or more disjoint
    paths, each represented as a list of alternating ``x, y`` coordinates.
    """

    SUBTYPE: str = "Ink"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- /InkList ----------

    def set_ink_list(self, inklist: Iterable[Iterable[float]] | None) -> None:
        """Set the freehand "scribble" path list (``/InkList``).

        Mirrors upstream ``setInkList(List<float[]>)`` (Java line 119).
        """
        if inklist is None:
            self._annot.remove_item(_INKLIST)
            return
        new_inklist = COSArray()
        for path in inklist:
            arr = COSArray()
            for value in path:
                arr.add(COSFloat(float(value)))
            new_inklist.add(arr)
        self._annot.set_item(_INKLIST, new_inklist)

    def get_ink_list(self) -> list[list[float]] | None:
        """Return the freehand paths, or ``None`` when ``/InkList`` is absent.

        Mirrors upstream ``getInkList()`` (Java line 137).
        """
        array = self._annot.get_dictionary_object(_INKLIST)
        if not isinstance(array, COSArray):
            return None
        out: list[list[float]] = []
        for entry in array:
            if isinstance(entry, COSArray):
                out.append(list(entry.to_float_array()))
            else:
                out.append([])
        return out


__all__ = ["FDFAnnotationInk"]

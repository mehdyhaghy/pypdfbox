from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .fdf_annotation import FDFAnnotation, _float_values

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_IC: COSName = COSName.get_pdf_name("IC")
_RD: COSName = COSName.get_pdf_name("RD")


class FDFAnnotationCircle(FDFAnnotation):
    """FDF circle annotation — ``/Subtype /Circle``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationCircle``.
    """

    SUBTYPE: str = "Circle"

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)
        if annot is None or annot.get_dictionary_object(_SUBTYPE) is None:
            self.set_subtype(self.SUBTYPE)

    # ---------- /IC interior colour ----------

    def get_interior_color(self) -> tuple[float, float, float] | None:
        v = self._annot.get_dictionary_object(_IC)
        if isinstance(v, COSArray) and len(v) == 3:
            values = _float_values(v, 3)
            if values is not None:
                return (values[0], values[1], values[2])
        return None

    def has_interior_color(self) -> bool:
        return self.get_interior_color() is not None

    def clear_interior_color(self) -> None:
        self.set_interior_color(None)

    def set_interior_color(self, color: tuple[float, float, float] | None) -> None:
        if color is None:
            self._annot.remove_item(_IC)
            return
        arr = COSArray()
        for v in color:
            arr.add(COSFloat(float(v)))
        self._annot.set_item(_IC, arr)

    # ---------- /RD fringe rectangle ----------

    def get_fringe(self) -> PDRectangle | None:
        v = self._annot.get_dictionary_object(_RD)
        if isinstance(v, COSArray) and len(v) >= 4:
            try:
                return PDRectangle.from_cos_array(v)
            except (TypeError, ValueError):
                return None
        return None

    def set_fringe(self, fringe: PDRectangle | None) -> None:
        if fringe is None:
            self._annot.remove_item(_RD)
            return
        self._annot.set_item(_RD, fringe.to_cos_array())

    def init_fringe(self, fringe: str | None) -> None:
        """Initialise /RD from an XFDF ``fringe`` attribute string.

        Mirrors upstream ``initFringe(Element)`` (Java lines 81-90). Accepts
        the attribute value directly (comma-separated 4-tuple); empty / None
        is a no-op so callers can forward ``element.getAttribute("fringe")``.
        Raises :class:`OSError` (Python equivalent of Java ``IOException``)
        when the value is not exactly four floats.
        """
        if fringe is None or not fringe:
            return
        rect = self.create_rectangle_from_attributes(
            fringe, "Error: wrong amount of numbers in attribute 'fringe'"
        )
        self.set_fringe(rect)


__all__ = ["FDFAnnotationCircle"]

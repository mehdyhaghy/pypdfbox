from __future__ import annotations

from collections.abc import Iterable

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .fdf_annotation import FDFAnnotation

_QUADPOINTS: COSName = COSName.get_pdf_name("QuadPoints")


class FDFAnnotationTextMarkup(FDFAnnotation):
    """FDF text-markup annotation base — common quad-point helper.

    Mirrors abstract ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotationTextMarkup``
    (Java lines 31-110). Subtype-specific subclasses (Highlight, Underline,
    Squiggly, StrikeOut) extend this; the base handles the ``/QuadPoints``
    array describing the quadrilaterals over the marked-up text.
    """

    def __init__(self, annot: COSDictionary | None = None) -> None:
        super().__init__(annot)

    # ---------- /QuadPoints ----------

    def set_coords(self, coords: Iterable[float] | None) -> None:
        """Set the quad-point coordinates (``/QuadPoints``).

        The array contains ``8 * n`` floats describing ``n`` quadrilaterals,
        each as ``x1 y1 x2 y2 x3 y3 x4 y4``. Mirrors upstream
        ``setCoords(float[])`` (Java line 84).
        """
        if coords is None:
            self._annot.remove_item(_QUADPOINTS)
            return
        new_quad_points = COSArray()
        for value in coords:
            new_quad_points.add(COSFloat(float(value)))
        self._annot.set_item(_QUADPOINTS, new_quad_points)

    def get_coords(self) -> list[float] | None:
        """Return the quad-point coordinates, or ``None`` if absent.

        Mirrors upstream ``getCoords()`` (Java line 97).
        """
        array = self._annot.get_dictionary_object(_QUADPOINTS)
        if isinstance(array, COSArray):
            return list(array.to_float_array())
        return None


__all__ = ["FDFAnnotationTextMarkup"]

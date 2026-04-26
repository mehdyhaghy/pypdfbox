from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup

_QUAD_POINTS: COSName = COSName.get_pdf_name("QuadPoints")


class PDAnnotationTextMarkup(PDAnnotationMarkup):
    """
    Intermediate base for the four text-markup annotation subtypes:
    Highlight, Underline, Strikeout, Squiggly. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationTextMarkup``.

    Text markup annotations carry a required ``/QuadPoints`` array of
    ``8 * n`` floats describing the quadrilaterals over which the markup
    is rendered (PDF 32000-1:2008 §12.5.6.10).

    Abstract — concrete subclasses set their own ``SUB_TYPE`` and
    ``/Subtype``.
    """

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        # Subtype is set by concrete subclasses, not here.

    # ---------- /QuadPoints ----------

    def get_quad_points(self) -> list[float] | None:
        value = self._dict.get_dictionary_object(_QUAD_POINTS)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_quad_points(self, qp: list[float] | tuple[float, ...] | None) -> None:
        if qp is None:
            self._dict.remove_item(_QUAD_POINTS)
            return
        arr = COSArray([COSFloat(float(v)) for v in qp])
        self._dict.set_item(_QUAD_POINTS, arr)


__all__ = ["PDAnnotationTextMarkup"]

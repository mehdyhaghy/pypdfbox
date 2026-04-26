from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup

_VERTICES: COSName = COSName.get_pdf_name("Vertices")


class PDAnnotationPolygon(PDAnnotationMarkup):
    """``/Subtype /Polygon`` annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon``.

    ``/Vertices`` is a flat array of alternating x/y float coordinates
    describing the polygon's vertices (PDF 32000-1:2008 §12.5.6.9).
    """

    SUB_TYPE: str = "Polygon"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /Vertices ----------

    def get_vertices(self) -> list[float] | None:
        value = self._dict.get_dictionary_object(_VERTICES)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_vertices(self, v: list[float] | tuple[float, ...] | None) -> None:
        if v is None:
            self._dict.remove_item(_VERTICES)
            return
        arr = COSArray([COSFloat(float(x)) for x in v])
        self._dict.set_item(_VERTICES, arr)


__all__ = ["PDAnnotationPolygon"]

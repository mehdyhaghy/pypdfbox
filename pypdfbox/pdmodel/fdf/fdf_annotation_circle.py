from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .fdf_annotation import FDFAnnotation

_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_IC: COSName = COSName.get_pdf_name("IC")


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
            return (
                _as_float(v[0]),
                _as_float(v[1]),
                _as_float(v[2]),
            )
        return None

    def set_interior_color(self, color: tuple[float, float, float] | None) -> None:
        if color is None:
            self._annot.remove_item(_IC)
            return
        arr = COSArray()
        for v in color:
            arr.add(COSFloat(float(v)))
        self._annot.set_item(_IC, arr)


def _as_float(v: object) -> float:
    val = getattr(v, "value", None)
    if isinstance(val, (int, float)):
        return float(val)
    return 0.0


__all__ = ["FDFAnnotationCircle"]

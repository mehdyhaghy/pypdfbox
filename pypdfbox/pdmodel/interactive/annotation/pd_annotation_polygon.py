from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup
from .pd_border_style_dictionary import PDBorderStyleDictionary

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
        PDMeasureDictionary,
    )

_VERTICES: COSName = COSName.get_pdf_name("Vertices")
_IC: COSName = COSName.get_pdf_name("IC")
_BS: COSName = COSName.get_pdf_name("BS")
_BE: COSName = COSName.get_pdf_name("BE")
_MEASURE: COSName = COSName.get_pdf_name("Measure")


class PDAnnotationPolygon(PDAnnotationMarkup):
    """``/Subtype /Polygon`` annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon``.

    ``/Vertices`` is a flat array of alternating x/y float coordinates
    describing the polygon's vertices (PDF 32000-1:2008 §12.5.6.9,
    Table 174).

    ``/IC`` (interior color), ``/BS`` (border style), ``/BE`` (border
    effect), ``/IT`` (intent — inherited from
    :class:`PDAnnotationMarkup`) and ``/Measure`` (measure dictionary)
    are also exposed. Per spec, polygon annotations do not carry ``/LE``
    (closed shape — no line endings).
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

    # ---------- /IC (interior color) ----------

    def get_interior_color(self) -> tuple[float, float, float] | None:
        """Return the 3-element ``[r, g, b]`` interior color or ``None``
        when unset. Typed ``PDColor`` lands with the rendering cluster
        (PRD §6.12); this lite accessor returns plain floats."""
        value = self._dict.get_dictionary_object(_IC)
        if isinstance(value, COSArray) and value.size() >= 3:
            comps = value.to_float_array()[:3]
            return (comps[0], comps[1], comps[2])
        return None

    def set_interior_color(
        self, rgb: tuple[float, float, float] | list[float] | None
    ) -> None:
        if rgb is None:
            self._dict.remove_item(_IC)
            return
        arr = COSArray([COSFloat(float(c)) for c in rgb])
        self._dict.set_item(_IC, arr)

    # ---------- /BS (border style) ----------

    def get_border_style(self) -> PDBorderStyleDictionary | None:
        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return PDBorderStyleDictionary(value)
        return None

    def set_border_style(
        self, bs: PDBorderStyleDictionary | COSDictionary | None
    ) -> None:
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(
            _BS,
            bs.get_cos_object() if hasattr(bs, "get_cos_object") else bs,
        )

    # ---------- /BE (border effect) ----------

    def get_border_effect(self) -> COSDictionary | None:
        """Raw border-effect dict — typed ``PDBorderEffectDictionary`` is
        deferred."""
        value = self._dict.get_dictionary_object(_BE)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_border_effect(self, be: COSDictionary | None) -> None:
        if be is None:
            self._dict.remove_item(_BE)
            return
        self._dict.set_item(_BE, be)

    # ---------- /Measure ----------

    def get_measure(self) -> "PDMeasureDictionary | None":
        """Return the typed measure dictionary or ``None`` when ``/Measure``
        is absent."""
        from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (  # noqa: PLC0415
            PDMeasureDictionary,
        )

        value = self._dict.get_dictionary_object(_MEASURE)
        if isinstance(value, COSDictionary):
            return PDMeasureDictionary(value)
        return None

    def set_measure(
        self, measure: "PDMeasureDictionary | COSDictionary | None"
    ) -> None:
        if measure is None:
            self._dict.remove_item(_MEASURE)
            return
        self._dict.set_item(
            _MEASURE,
            measure.get_cos_object() if hasattr(measure, "get_cos_object") else measure,
        )


__all__ = ["PDAnnotationPolygon"]

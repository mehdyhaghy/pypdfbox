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
_LE: COSName = COSName.get_pdf_name("LE")
_MEASURE: COSName = COSName.get_pdf_name("Measure")

_LE_NONE: str = "None"


class PDAnnotationPolyline(PDAnnotationMarkup):
    """``/Subtype /PolyLine`` annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline``.

    Note the PDF spec capitalization: ``PolyLine`` (not ``Polyline``).

    ``/Vertices`` is a flat array of alternating x/y float coordinates
    describing the polyline's vertices (PDF 32000-1:2008 §12.5.6.9,
    Table 175).

    Also exposed: ``/IC`` (interior color), ``/BS`` (border style),
    ``/BE`` (border effect), ``/LE`` (line-ending styles for the open
    polyline endpoints), ``/IT`` (intent — inherited from
    :class:`PDAnnotationMarkup`) and ``/Measure``.
    """

    SUB_TYPE: str = "PolyLine"

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

    # ---------- /LE (line-ending styles) ----------

    def get_line_ending_styles(self) -> tuple[str, str] | None:
        """Return ``(start, end)`` line-ending style names or ``None`` when
        ``/LE`` is absent. See ``PDAnnotationLine`` for the legal style
        constants (Table 176)."""
        value = self._dict.get_dictionary_object(_LE)
        if isinstance(value, COSArray) and value.size() >= 2:
            start = value.get(0)
            end = value.get(1)
            start_name = start.name if isinstance(start, COSName) else _LE_NONE
            end_name = end.name if isinstance(end, COSName) else _LE_NONE
            return (start_name, end_name)
        return None

    def set_line_ending_styles(self, start: str, end: str) -> None:
        arr = COSArray(
            [COSName.get_pdf_name(start), COSName.get_pdf_name(end)]
        )
        self._dict.set_item(_LE, arr)

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


__all__ = ["PDAnnotationPolyline"]

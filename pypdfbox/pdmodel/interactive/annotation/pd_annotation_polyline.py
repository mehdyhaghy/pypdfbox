from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup
from .pd_border_effect_dictionary import PDBorderEffectDictionary
from .pd_border_style_dictionary import PDBorderStyleDictionary

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
        PDMeasureDictionary,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .handlers.pd_appearance_handler import PDAppearanceHandler

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
        self._custom_appearance_handler: PDAppearanceHandler | None = None
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

    def get_border_effect(self) -> PDBorderEffectDictionary | None:
        """Return the ``/BE`` border-effect dictionary wrapped in
        :class:`PDBorderEffectDictionary`. Upstream
        :class:`org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline`
        does not expose ``/BE``; we surface the typed accessor here for
        parity with :class:`PDAnnotationPolygon` and the polyline
        appearance handlers that consume ``/BE`` when present.
        Returns ``None`` when ``/BE`` is absent."""
        value = self._dict.get_dictionary_object(_BE)
        if isinstance(value, COSDictionary):
            return PDBorderEffectDictionary(value)
        return None

    def set_border_effect(
        self, be: PDBorderEffectDictionary | COSDictionary | None
    ) -> None:
        """Set ``/BE`` from a :class:`PDBorderEffectDictionary` or a raw
        ``COSDictionary``."""
        if be is None:
            self._dict.remove_item(_BE)
            return
        self._dict.set_item(
            _BE,
            be.get_cos_object() if hasattr(be, "get_cos_object") else be,
        )

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

    # ---------- /LE individual endpoint accessors (upstream parity) ----------

    def _set_le_entry(self, index: int, style: str | None) -> None:
        actual = _LE_NONE if style is None else style
        value = self._dict.get_dictionary_object(_LE)
        if not isinstance(value, COSArray) or value.size() < 2:
            arr = COSArray(
                [
                    COSName.get_pdf_name(_LE_NONE),
                    COSName.get_pdf_name(_LE_NONE),
                ]
            )
            arr.set(index, COSName.get_pdf_name(actual))
            self._dict.set_item(_LE, arr)
            return
        value.set(index, COSName.get_pdf_name(actual))

    def get_start_point_ending_style(self) -> str:
        """Return the line-ending style for the start point. Mirrors
        upstream ``getStartPointEndingStyle()`` — ``LE_NONE`` (``"None"``)
        when ``/LE`` is missing or short. See :class:`PDAnnotationLine`
        for the legal style constants (Table 176)."""
        value = self._dict.get_dictionary_object(_LE)
        if isinstance(value, COSArray) and value.size() >= 2:
            entry = value.get(0)
            if isinstance(entry, COSName):
                return entry.name
        return _LE_NONE

    def set_start_point_ending_style(self, style: str | None) -> None:
        """Set the line-ending style for the start point. Mirrors upstream
        ``setStartPointEndingStyle(String)`` — ``None`` is normalised to
        ``LE_NONE`` like upstream."""
        self._set_le_entry(0, style)

    def get_end_point_ending_style(self) -> str:
        """Return the line-ending style for the end point. Mirrors
        upstream ``getEndPointEndingStyle()`` — ``LE_NONE`` when ``/LE``
        is missing or short."""
        value = self._dict.get_dictionary_object(_LE)
        if isinstance(value, COSArray) and value.size() >= 2:
            entry = value.get(1)
            if isinstance(entry, COSName):
                return entry.name
        return _LE_NONE

    def set_end_point_ending_style(self, style: str | None) -> None:
        """Set the line-ending style for the end point. Mirrors upstream
        ``setEndPointEndingStyle(String)``."""
        self._set_le_entry(1, style)

    # ---------- /Measure ----------

    def get_measure(self) -> PDMeasureDictionary | None:
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
        self, measure: PDMeasureDictionary | COSDictionary | None
    ) -> None:
        if measure is None:
            self._dict.remove_item(_MEASURE)
            return
        self._dict.set_item(
            _MEASURE,
            measure.get_cos_object() if hasattr(measure, "get_cos_object") else measure,
        )

    # ---------- appearance construction ----------

    def set_custom_appearance_handler(
        self, appearance_handler: PDAppearanceHandler | None
    ) -> None:
        """Set the custom appearance handler used by
        :meth:`construct_appearances`.

        Mirrors upstream ``setCustomAppearanceHandler``
        (``PDAnnotationPolyline.java`` line 182). Pass ``None`` to clear
        the custom handler and restore the default construction path.
        """
        self._custom_appearance_handler = appearance_handler

    def get_custom_appearance_handler(self) -> PDAppearanceHandler | None:
        """Return the custom appearance handler previously set via
        :meth:`set_custom_appearance_handler`, or ``None`` when the default
        construction path is in use. No upstream getter exists (the field is
        package-private in Java); this is the Pythonic accessor used by
        tests and downstream code that needs to inspect the wired handler.
        """
        return self._custom_appearance_handler

    def construct_appearances(self, document: PDDocument | None = None) -> None:
        """Generate polyline annotation appearances.

        Mirrors upstream ``constructAppearances()`` /
        ``constructAppearances(PDDocument)``
        (``PDAnnotationPolyline.java`` lines 188-205): a custom handler,
        when configured, is invoked exactly as upstream does. The built-in
        ``PDPolylineAppearanceHandler`` is not ported yet, so the default
        path falls through to the base no-op.
        """
        if self._custom_appearance_handler is not None:
            self._custom_appearance_handler.generate_appearance_streams()
            return None
        return super().construct_appearances(document)


__all__ = ["PDAnnotationPolyline"]

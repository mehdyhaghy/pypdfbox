from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSName,
    COSNumber,
)

from .pd_annotation_markup import PDAnnotationMarkup

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
        PDMeasureDictionary,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .handlers.pd_appearance_handler import PDAppearanceHandler

_L: COSName = COSName.get_pdf_name("L")
_LE: COSName = COSName.get_pdf_name("LE")
_CAP: COSName = COSName.get_pdf_name("Cap")
_CO: COSName = COSName.get_pdf_name("CO")
_LL: COSName = COSName.get_pdf_name("LL")
_LLE: COSName = COSName.get_pdf_name("LLE")
_LLO: COSName = COSName.get_pdf_name("LLO")
_CP: COSName = COSName.get_pdf_name("CP")
_IC: COSName = COSName.get_pdf_name("IC")
_MEASURE: COSName = COSName.get_pdf_name("Measure")


class PDAnnotationLine(PDAnnotationMarkup):
    """
    Line annotation — ``/Subtype /Line``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine``.

    A line annotation displays a single straight line on the page,
    optionally decorated with end-point styles (arrows, circles, …) and a
    caption (PDF 32000-1:2008 §12.5.6.7).

    Cluster #5 lite: exposes the core line geometry, end-point styles,
    caption flag/offsets, leader-line lengths, interior colour, measurement
    dictionary, and intent helpers. Border style (``/BS``) is inherited from
    :class:`PDAnnotationMarkup`; border effect dictionaries and appearance
    generation are deferred.
    """

    SUB_TYPE: str = "Line"

    # ---------- /IT intent constants (Table 174) ----------

    IT_LINE_ARROW: str = "LineArrow"
    IT_LINE_DIMENSION: str = "LineDimension"

    # ---------- /LE line-ending style constants (Table 176) ----------

    LE_NONE: str = "None"
    LE_SQUARE: str = "Square"
    LE_CIRCLE: str = "Circle"
    LE_DIAMOND: str = "Diamond"
    LE_OPEN_ARROW: str = "OpenArrow"
    LE_CLOSED_ARROW: str = "ClosedArrow"
    LE_BUTT: str = "Butt"
    LE_R_OPEN_ARROW: str = "ROpenArrow"
    LE_R_CLOSED_ARROW: str = "RClosedArrow"
    LE_SLASH: str = "Slash"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        self._custom_appearance_handler: PDAppearanceHandler | None = None
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)
            # Mirror upstream: ``/L`` is mandatory per PDF 32000 — upstream
            # seeds it with ``[0, 0, 0, 0]`` so the constructed annotation
            # is spec-valid before callers fill in real coordinates.
            self.set_line([0.0, 0.0, 0.0, 0.0])

    # ---------- /L (line coordinates) ----------

    def get_line(self) -> list[float] | None:
        """Return the ``/L`` line coordinates or ``None`` when unset.

        Mirrors upstream ``PDAnnotationLine.getLine()`` (Java bytecode):
        when ``/L`` is a COSArray the WHOLE array is returned via
        ``toFloatArray()`` — no arity check and no slicing — so a malformed
        2- or 6-element ``/L`` round-trips byte-for-byte with PDFBox (a
        well-formed ``/L`` is the spec's 4-element ``[x1 y1 x2 y2]``). Non-
        numeric members become ``0.0`` (COSArray.toFloatArray convention).
        Returns ``None`` only when ``/L`` is absent or not an array."""
        value = self._dict.get_dictionary_object(_L)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_line(self, line: list[float] | tuple[float, ...]) -> None:
        """Set ``/L`` to the supplied 4-element ``[x1, y1, x2, y2]``."""
        if len(line) != 4:
            raise ValueError(
                f"/L must be a 4-element [x1 y1 x2 y2] array; got {len(line)} elements"
            )
        arr = COSArray([COSFloat(float(c)) for c in line])
        self._dict.set_item(_L, arr)

    # ---------- /LE (line ending styles) ----------

    def _get_le_array(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_LE)
        if isinstance(value, COSArray):
            return value
        return None

    def _set_le_entry(self, index: int, style: str) -> None:
        arr = self._get_le_array()
        if arr is None:
            arr = COSArray(
                [
                    COSName.get_pdf_name(self.LE_NONE),
                    COSName.get_pdf_name(self.LE_NONE),
                ]
            )
            self._dict.set_item(_LE, arr)
        # Pad if the existing array is too short.
        while arr.size() <= index:
            arr.add(COSName.get_pdf_name(self.LE_NONE))
        arr.set(index, COSName.get_pdf_name(style))

    def get_start_point_ending_style(self) -> str:
        """Default per spec is ``None``."""
        arr = self._get_le_array()
        if arr is not None and arr.size() >= 1:
            entry = arr.get(0)
            if isinstance(entry, COSName):
                return entry.name
        return self.LE_NONE

    def set_start_point_ending_style(self, style: str | None) -> None:
        """Set the line-ending style for the start point. Mirrors upstream
        ``setStartPointEndingStyle(String)`` — passing ``None`` is
        coerced to :data:`LE_NONE` to match upstream's null-coalescing."""
        actual_style = self.LE_NONE if style is None else style
        self._set_le_entry(0, actual_style)

    def get_end_point_ending_style(self) -> str:
        """Default per spec is ``None``."""
        arr = self._get_le_array()
        if arr is not None and arr.size() >= 2:
            entry = arr.get(1)
            if isinstance(entry, COSName):
                return entry.name
        return self.LE_NONE

    def set_end_point_ending_style(self, style: str | None) -> None:
        """Set the line-ending style for the end point. Mirrors upstream
        ``setEndPointEndingStyle(String)`` — passing ``None`` is coerced
        to :data:`LE_NONE` to match upstream's null-coalescing."""
        actual_style = self.LE_NONE if style is None else style
        self._set_le_entry(1, actual_style)

    # ---------- /Cap (caption flag) ----------

    def get_caption(self) -> bool:
        """Default per spec is ``False``."""
        return self._dict.get_boolean(_CAP, False)

    def set_caption(self, value: bool) -> None:
        self._dict.set_item(_CAP, COSBoolean.get(value))

    def has_caption(self) -> bool:
        """Upstream-named accessor for ``/Cap``. Mirrors
        ``hasCaption()`` — whether the contents shall be shown as a
        caption in the appearance of the line."""
        return self.get_caption()

    # ---------- /CO (caption offset) ----------

    def _get_co_array(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_CO)
        if isinstance(value, COSArray):
            return value
        return None

    def _set_co_entry(self, index: int, offset: float) -> None:
        arr = self._get_co_array()
        if arr is None:
            arr = COSArray([COSFloat(0.0), COSFloat(0.0)])
            self._dict.set_item(_CO, arr)
        while arr.size() <= index:
            arr.add(COSFloat(0.0))
        arr.set(index, COSFloat(float(offset)))

    def get_caption_horizontal_offset(self) -> float:
        arr = self._get_co_array()
        if arr is not None and arr.size() >= 1:
            entry = arr.get(0)
            if isinstance(entry, COSNumber):
                return entry.float_value()
        return 0.0

    def set_caption_horizontal_offset(self, offset: float) -> None:
        self._set_co_entry(0, offset)

    def get_caption_vertical_offset(self) -> float:
        arr = self._get_co_array()
        if arr is not None and arr.size() >= 2:
            entry = arr.get(1)
            if isinstance(entry, COSNumber):
                return entry.float_value()
        return 0.0

    def set_caption_vertical_offset(self, offset: float) -> None:
        self._set_co_entry(1, offset)

    # ---------- /LL (leader line length) ----------

    def get_leader_line_length(self) -> float:
        return self._dict.get_float(_LL, 0.0)

    def set_leader_line_length(self, length: float) -> None:
        self._dict.set_float(_LL, float(length))

    # ---------- /LLE (leader line extension length) ----------

    def get_leader_line_extension_length(self) -> float:
        return self._dict.get_float(_LLE, 0.0)

    def set_leader_line_extension_length(self, length: float) -> None:
        self._dict.set_float(_LLE, float(length))

    # ---------- /LLO (leader line offset length) ----------

    def get_leader_line_offset_length(self) -> float:
        """Mirrors upstream ``getLeaderLineOffsetLength()`` — default
        ``0`` per spec when ``/LLO`` is absent."""
        return self._dict.get_float(_LLO, 0.0)

    def set_leader_line_offset_length(self, length: float) -> None:
        """Mirrors upstream ``setLeaderLineOffsetLength(float)``."""
        self._dict.set_float(_LLO, float(length))

    # ---------- /CP (caption positioning) ----------

    def get_caption_positioning(self) -> str | None:
        """Mirrors upstream ``getCaptionPositioning()`` — returns the
        ``/CP`` name (``"Inline"`` or ``"Top"``), or ``None`` when
        unset."""
        return self._dict.get_name_as_string(_CP)

    def set_caption_positioning(self, caption_positioning: str | None) -> None:
        """Mirrors upstream ``setCaptionPositioning(String)``. Allowed
        values are ``"Inline"`` and ``"Top"``."""
        if caption_positioning is None:
            self._dict.remove_item(_CP)
            return
        self._dict.set_name(_CP, caption_positioning)

    # ---------- /IC (interior color of line endings) ----------

    def get_interior_color(self) -> list[float] | None:
        """Return the ``/IC`` interior-color components for the line endings
        defined by ``/LE``. Mirrors upstream ``getInteriorColor()`` —
        upstream returns a typed ``PDColor`` (rendering cluster). This lite
        accessor returns plain floats; component count implies the colour
        space (1 = DeviceGray, 3 = DeviceRGB, 4 = DeviceCMYK).
        Returns ``None`` when ``/IC`` is absent."""
        value = self._dict.get_dictionary_object(_IC)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_interior_color(
        self, ic: list[float] | tuple[float, ...] | None
    ) -> None:
        """Set the ``/IC`` interior-color array. Mirrors upstream
        ``setInteriorColor(PDColor)``. Pass ``None`` to clear the entry."""
        if ic is None:
            self._dict.remove_item(_IC)
            return
        arr = COSArray([COSFloat(float(c)) for c in ic])
        self._dict.set_item(_IC, arr)

    # ---------- /Measure (measurement dictionary) ----------

    def get_measure(self) -> PDMeasureDictionary | None:
        """Return the typed ``/Measure`` dictionary (PDF 32000-2 Table 174
        — line measurement) or ``None`` when the entry is absent.

        Mirrors the typed accessor exposed on
        :class:`PDAnnotationPolygon`/:class:`PDAnnotationPolyline`.
        """
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
        """Set or clear the ``/Measure`` dictionary. Pass ``None`` to remove
        the entry; accepts both a typed :class:`PDMeasureDictionary` (via
        ``get_cos_object``) and a raw :class:`COSDictionary`."""
        if measure is None:
            self._dict.remove_item(_MEASURE)
            return
        self._dict.set_item(
            _MEASURE,
            measure.get_cos_object() if hasattr(measure, "get_cos_object") else measure,
        )

    # ---------- /IT (intent) predicates ----------

    def is_line_arrow(self) -> bool:
        """Predicate for ``/IT == "LineArrow"``. No upstream equivalent —
        saves callers from comparing :meth:`get_intent` against
        :data:`IT_LINE_ARROW` by hand."""
        return self.get_intent() == self.IT_LINE_ARROW

    def is_line_dimension(self) -> bool:
        """Predicate for ``/IT == "LineDimension"``. No upstream equivalent —
        saves callers from comparing :meth:`get_intent` against
        :data:`IT_LINE_DIMENSION` by hand."""
        return self.get_intent() == self.IT_LINE_DIMENSION

    # ---------- appearance construction ----------

    def set_custom_appearance_handler(
        self, appearance_handler: PDAppearanceHandler | None
    ) -> None:
        """Set the custom appearance handler used by
        :meth:`construct_appearances`.

        Mirrors upstream ``setCustomAppearanceHandler``
        (``PDAnnotationLine.java`` line 416). Pass ``None`` to clear the
        custom handler and restore the default construction path.
        """
        self._custom_appearance_handler = appearance_handler

    def get_custom_appearance_handler(self) -> PDAppearanceHandler | None:
        """Return the custom appearance handler previously set via
        :meth:`set_custom_appearance_handler`, or ``None`` when the default
        construction path is in use. No upstream getter exists (the field is
        private in Java); this is the Pythonic accessor used by tests and
        downstream code that needs to inspect the wired handler.
        """
        return self._custom_appearance_handler

    def construct_appearances(self, document: PDDocument | None = None) -> None:
        """Generate line annotation appearances.

        Mirrors upstream ``constructAppearances()`` and
        ``constructAppearances(PDDocument)`` (``PDAnnotationLine.java``
        lines 422-438). A custom handler, when configured, is invoked
        exactly as upstream does; otherwise the built-in
        :class:`PDLineAppearanceHandler` generates the ``/AP`` streams.
        """
        if self._custom_appearance_handler is not None:
            self._custom_appearance_handler.generate_appearance_streams()
            return None
        from .handlers.pd_line_appearance_handler import (
            PDLineAppearanceHandler,
        )

        PDLineAppearanceHandler(self, document).generate_appearance_streams()
        return None


__all__ = ["PDAnnotationLine"]

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup
from .pd_border_effect_dictionary import PDBorderEffectDictionary
from .pd_border_style_dictionary import PDBorderStyleDictionary

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary import (
        PDMeasureDictionary,
    )

_VERTICES: COSName = COSName.get_pdf_name("Vertices")
_IC: COSName = COSName.get_pdf_name("IC")
_BS: COSName = COSName.get_pdf_name("BS")
_BE: COSName = COSName.get_pdf_name("BE")
_PATH: COSName = COSName.get_pdf_name("Path")
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

    def get_border_effect(self) -> PDBorderEffectDictionary | None:
        """Return the ``/BE`` border-effect dictionary wrapped in
        :class:`PDBorderEffectDictionary`. Mirrors upstream
        ``getBorderEffect()``. Returns ``None`` when ``/BE`` is absent."""
        value = self._dict.get_dictionary_object(_BE)
        if isinstance(value, COSDictionary):
            return PDBorderEffectDictionary(value)
        return None

    def set_border_effect(
        self, be: PDBorderEffectDictionary | COSDictionary | None
    ) -> None:
        """Set ``/BE`` from a :class:`PDBorderEffectDictionary` or a raw
        ``COSDictionary``. Mirrors upstream ``setBorderEffect(PDBorderEffectDictionary)``."""
        if be is None:
            self._dict.remove_item(_BE)
            return
        self._dict.set_item(
            _BE,
            be.get_cos_object() if hasattr(be, "get_cos_object") else be,
        )

    # ---------- /Path (PDF 2.0) ----------

    def get_path(self) -> list[list[float]] | None:
        """PDF 2.0: return the ``/Path`` operands array — a list where each
        inner list supplies operands for a path-building operator
        (``m``, ``l`` or ``c``). The first inner list has 2 elements; the
        rest have 2 or 6. Returns ``None`` when ``/Path`` is absent.

        Mirrors upstream ``getPath()`` returning ``float[][]``.
        """
        value = self._dict.get_dictionary_object(_PATH)
        if not isinstance(value, COSArray):
            return None
        result: list[list[float]] = []
        for i in range(value.size()):
            item = value.get(i)
            if isinstance(item, COSArray):
                result.append(item.to_float_array())
            else:
                result.append([])
        return result

    def set_path(self, path: Sequence[Sequence[float]] | None) -> None:
        """Set the PDF 2.0 ``/Path`` operands array.

        Mirrors upstream ``setPath(float[][])``. Passing ``None`` clears the
        entry.
        """
        if path is None:
            self._dict.remove_item(_PATH)
            return
        outer = COSArray()
        for operands in path:
            outer.add(COSArray([COSFloat(float(operand)) for operand in operands]))
        self._dict.set_item(_PATH, outer)

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

    # ---------- predicates / vertex helpers ----------

    def has_vertices(self) -> bool:
        """``True`` when ``/Vertices`` is present (regardless of contents).

        Predicate companion to :meth:`get_vertices`; useful for callers
        that need to distinguish "polygon never authored" from "polygon
        authored with an empty/malformed vertices array".
        """
        return self._dict.get_dictionary_object(_VERTICES) is not None

    def vertex_count(self) -> int:
        """Return the number of ``(x, y)`` vertex points in ``/Vertices``.

        ``/Vertices`` stores alternating x/y floats, so this is
        ``len(/Vertices) // 2``. Returns ``0`` when ``/Vertices`` is
        absent or not a ``COSArray``. Trailing odd entries are dropped to
        match the spec which mandates an even number of coordinates.
        """
        value = self._dict.get_dictionary_object(_VERTICES)
        if isinstance(value, COSArray):
            return value.size() // 2
        return 0

    def iter_vertex_points(self) -> list[tuple[float, float]]:
        """Return ``/Vertices`` as a list of ``(x, y)`` tuples.

        Convenience helper — upstream callers manipulate the flat
        ``float[]`` directly, but Python callers usually want point
        pairs. Returns an empty list when ``/Vertices`` is absent or
        malformed. Trailing odd entries are dropped.
        """
        value = self._dict.get_dictionary_object(_VERTICES)
        if not isinstance(value, COSArray):
            return []
        coords = value.to_float_array()
        pairs: list[tuple[float, float]] = []
        for i in range(0, len(coords) - 1, 2):
            pairs.append((coords[i], coords[i + 1]))
        return pairs

    def has_path(self) -> bool:
        """``True`` when the PDF 2.0 ``/Path`` entry is present.

        Predicate companion to :meth:`get_path`. ``/Path`` is mutually
        exclusive with ``/Vertices`` per PDF 2.0 — if both are present
        readers should use ``/Path``.
        """
        return self._dict.get_dictionary_object(_PATH) is not None

    def has_border_effect(self) -> bool:
        """``True`` when the ``/BE`` border-effect dictionary is present."""
        return self._dict.get_dictionary_object(_BE) is not None

    def has_interior_color(self) -> bool:
        """``True`` when the ``/IC`` interior-color array is present."""
        return self._dict.get_dictionary_object(_IC) is not None

    def has_measure(self) -> bool:
        """``True`` when the ``/Measure`` dictionary is present."""
        return self._dict.get_dictionary_object(_MEASURE) is not None


__all__ = ["PDAnnotationPolygon"]

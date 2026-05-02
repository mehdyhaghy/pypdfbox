from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .pd_annotation_line import PDAnnotationLine
from .pd_annotation_markup import PDAnnotationMarkup
from .pd_border_effect_dictionary import PDBorderEffectDictionary
from .pd_border_style_dictionary import PDBorderStyleDictionary

_DA: COSName = COSName.get_pdf_name("DA")
_Q: COSName = COSName.get_pdf_name("Q")
_DS: COSName = COSName.get_pdf_name("DS")
_RC: COSName = COSName.get_pdf_name("RC")
_IT: COSName = COSName.get_pdf_name("IT")
_CL: COSName = COSName.get_pdf_name("CL")
_LE: COSName = COSName.get_pdf_name("LE")
_BS: COSName = COSName.get_pdf_name("BS")
_BE: COSName = COSName.get_pdf_name("BE")
_RD: COSName = COSName.get_pdf_name("RD")


class PDAnnotationFreeText(PDAnnotationMarkup):
    """
    FreeText annotation — ``/Subtype /FreeText``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFreeText``.

    A free-text annotation displays text directly on the page rather than
    in a popup (PDF 32000-1:2008 §12.5.6.6). Exposes ``/DA``, ``/Q``,
    ``/DS``, ``/RC``, ``/IT``, ``/CL``, ``/LE``, ``/BS``, ``/BE`` and
    ``/RD``. Appearance generation is deferred. ``/BE`` is exposed as a
    raw :class:`COSDictionary` until ``PDBorderEffectDictionary`` is
    ported.
    """

    SUB_TYPE: str = "FreeText"

    # ---------- /Q justification constants (Table 174) ----------

    JUSTIFICATION_LEFT: int = 0
    JUSTIFICATION_CENTER: int = 1
    JUSTIFICATION_RIGHT: int = 2

    # ---------- /IT intent constants (Table 174) ----------

    IT_FREE_TEXT: str = "FreeText"
    IT_FREE_TEXT_PLAIN: str = IT_FREE_TEXT
    IT_FREE_TEXT_CALLOUT: str = "FreeTextCallout"
    IT_FREE_TEXT_TYPE_WRITER: str = "FreeTextTypeWriter"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /DA (default appearance string) ----------

    def get_default_appearance(self) -> str | None:
        return self._dict.get_string(_DA)

    def set_default_appearance(self, default_appearance: str | None) -> None:
        self._dict.set_string(_DA, default_appearance)

    # ---------- /Q (quadding / justification) ----------

    def get_q(self) -> int:
        """Default per spec is ``0`` (left-justified)."""
        return self._dict.get_int(_Q, self.JUSTIFICATION_LEFT)

    def set_q(self, q: int) -> None:
        self._dict.set_int(_Q, int(q))

    # ---------- /DS (default style string) ----------

    def get_default_style_string(self) -> str | None:
        return self._dict.get_string(_DS)

    def set_default_style_string(self, default_style_string: str | None) -> None:
        self._dict.set_string(_DS, default_style_string)

    # ---------- /RC (rich-text contents) ----------

    def get_rich_contents(self) -> str | None:
        return self._dict.get_string(_RC)

    def set_rich_contents(self, rich_contents: str | None) -> None:
        self._dict.set_string(_RC, rich_contents)

    # ---------- /IT (intent) ----------

    def get_intent(self) -> str | None:
        return self._dict.get_name(_IT)

    def set_intent(self, intent: str | None) -> None:
        if intent is None:
            self._dict.remove_item(_IT)
            return
        self._dict.set_name(_IT, intent)

    # ---------- /CL (callout line) ----------

    def get_callout_line(self) -> list[float] | None:
        """Return the ``/CL`` callout-line coordinates.

        4 floats ``[x1, y1, x2, y2]`` for a 2-segment knee, or 6 floats
        ``[x1, y1, x2, y2, x3, y3]`` for a 3-segment knee. Returns
        ``None`` when ``/CL`` is absent or malformed.
        """
        value = self._dict.get_dictionary_object(_CL)
        if isinstance(value, COSArray):
            size = value.size()
            if size >= 6:
                return value.to_float_array()[:6]
            if size >= 4:
                return value.to_float_array()[:4]
        return None

    def set_callout_line(self, coords: list[float] | None) -> None:
        """Set ``/CL``. Accepts 4 or 6 floats; ``None`` clears the entry."""
        if coords is None:
            self._dict.remove_item(_CL)
            return
        arr = COSArray([COSFloat(float(c)) for c in coords])
        self._dict.set_item(_CL, arr)

    def get_callout(self) -> list[float] | None:
        """Upstream-named alias for :meth:`get_callout_line`."""
        return self.get_callout_line()

    def set_callout(self, callout: list[float] | None) -> None:
        """Upstream-named alias for :meth:`set_callout_line`."""
        self.set_callout_line(callout)

    # ---------- /LE (line ending style) ----------

    def get_line_ending(self) -> str:
        """Default per spec is ``None``."""
        value = self._dict.get_name(_LE)
        return value if value is not None else PDAnnotationLine.LE_NONE

    def set_line_ending(self, le: str) -> None:
        self._dict.set_name(_LE, le)

    def get_line_ending_style(self) -> str:
        """Upstream-named alias for :meth:`get_line_ending`."""
        return self.get_line_ending()

    def set_line_ending_style(self, style: str) -> None:
        """Upstream-named alias for :meth:`set_line_ending`."""
        self.set_line_ending(style)

    # ---------- /BS (border style dictionary) ----------

    def get_border_style(self) -> PDBorderStyleDictionary | None:
        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return PDBorderStyleDictionary(value)
        return None

    def set_border_style(self, bs: PDBorderStyleDictionary | None) -> None:
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(_BS, bs.get_cos_object())

    # ---------- /BE (border effect dictionary) ----------

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

    # ---------- /RD (rectangle differences) ----------

    def get_rectangle_differences(self) -> list[float] | None:
        """Return the 4-element ``[left, top, right, bottom]`` ``/RD``
        differences, or ``None`` when unset."""
        value = self._dict.get_dictionary_object(_RD)
        if isinstance(value, COSArray) and value.size() >= 4:
            return value.to_float_array()[:4]
        return None

    def set_rectangle_differences(self, diffs: list[float] | None) -> None:
        if diffs is None:
            self._dict.remove_item(_RD)
            return
        arr = COSArray([COSFloat(float(d)) for d in diffs])
        self._dict.set_item(_RD, arr)

    def get_rect_differences(self) -> list[float]:
        """Upstream-named accessor for ``/RD``.

        PDFBox returns an empty ``float[]`` when ``/RD`` is absent; keep the
        existing ``get_rectangle_differences`` ``None`` default for backward
        compatibility and expose the upstream default here.
        """
        return self.get_rectangle_differences() or []

    # ---------- /RD as PDRectangle (upstream singular accessors) ----------

    def get_rect_difference(self) -> PDRectangle | None:
        """Return the ``/RD`` entry as a :class:`PDRectangle`, or ``None``.

        Mirrors upstream's ``getRectDifference()``: ``/RD`` is stored as a
        4-element COSArray of left/top/right/bottom margins, and PDFBox
        wraps it in a ``PDRectangle`` for the singular-named accessor.
        Returns ``None`` when the entry is missing or has fewer than four
        numeric entries.
        """
        value = self._dict.get_dictionary_object(_RD)
        if isinstance(value, COSArray) and value.size() >= 4:
            return PDRectangle.from_cos_array(value)
        return None

    def set_rect_difference(self, rd: PDRectangle | None) -> None:
        """Set ``/RD`` from a :class:`PDRectangle`.

        Mirrors upstream's ``setRectDifference(PDRectangle rd)``. Passing
        ``None`` clears the entry.
        """
        if rd is None:
            self._dict.remove_item(_RD)
            return
        self._dict.set_item(_RD, rd.to_cos_array())

    def set_rect_differences(
        self, *differences: float | list[float] | None
    ) -> None:
        """Upstream-shaped setter for ``/RD``.

        Accepts either one float for all four sides, four explicit side
        values, an existing ``list[float]`` for Python callers, or ``None`` to
        clear the entry.
        """
        if len(differences) == 1:
            difference = differences[0]
            if difference is None:
                self.set_rectangle_differences(None)
                return
            if isinstance(difference, list):
                self.set_rectangle_differences(difference)
                return
            value = float(difference)
            self.set_rectangle_differences([value, value, value, value])
            return

        if len(differences) == 4:
            self.set_rectangle_differences([float(d) for d in differences])
            return

        raise TypeError("set_rect_differences expects 1 or 4 values")


__all__ = ["PDAnnotationFreeText"]

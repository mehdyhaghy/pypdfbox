from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .pd_annotation import PDAnnotation

_BS: COSName = COSName.get_pdf_name("BS")
_IC: COSName = COSName.get_pdf_name("IC")
_BE: COSName = COSName.get_pdf_name("BE")
_RD: COSName = COSName.get_pdf_name("RD")


class PDAnnotationSquareCircle(PDAnnotation):
    """
    Shared base for Square (``/Subtype /Square``) and Circle
    (``/Subtype /Circle``) annotations. Mirrors upstream's
    ``PDAnnotationSquareCircle`` which is also a single shared class.

    Upstream extends ``PDAnnotationMarkup``; cluster #5 lite skips the
    Markup intermediary and inherits straight from :class:`PDAnnotation`
    because the markup-specific accessors (``Popup``, ``RC``, ``CA``, …)
    aren't ported yet. See ``CHANGES.md``.
    """

    def __init__(
        self,
        sub_type: str | COSDictionary | None = None,
    ) -> None:
        if isinstance(sub_type, COSDictionary):
            super().__init__(sub_type)
        else:
            super().__init__(None)
            if sub_type is not None:
                self._set_subtype(sub_type)

    # ---------- /BS (border style) ----------

    def get_border_style(self) -> "PDBorderStyleDictionary | None":
        from .pd_border_style_dictionary import PDBorderStyleDictionary

        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return PDBorderStyleDictionary(value)
        return None

    def set_border_style(
        self, bs: "PDBorderStyleDictionary | COSDictionary | None"
    ) -> None:
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(
            _BS,
            bs.get_cos_object() if hasattr(bs, "get_cos_object") else bs,
        )

    # ---------- /IC (interior color) ----------

    def get_interior_color(self) -> COSArray | None:
        """Raw color components. Typed ``PDColor`` lands with rendering
        cluster (PRD §6.12)."""
        value = self._dict.get_dictionary_object(_IC)
        if isinstance(value, COSArray):
            return value
        return None

    def set_interior_color(self, ic: COSArray | None) -> None:
        if ic is None:
            self._dict.remove_item(_IC)
            return
        self._dict.set_item(_IC, ic)

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

    # ---------- /RD (rectangle difference) ----------

    def get_rect_difference(self) -> PDRectangle | None:
        """Return the ``/RD`` entry as a :class:`PDRectangle`, or ``None``.

        Mirrors upstream's ``getRectDifference()``. ``/RD`` is the
        difference between the annotation's outer ``/Rect`` and the area
        actually drawn (used to absorb border-effect padding). Returns
        ``None`` when ``/RD`` is missing or has fewer than four numeric
        entries.
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

    def get_rect_differences(self) -> list[float]:
        """Return ``/RD`` as a 4-element float list ``[left, top, right,
        bottom]``.

        Mirrors upstream's ``getRectDifferences()``: returns an empty list
        when the entry is absent (upstream returns ``new float[]{}``).
        """
        value = self._dict.get_dictionary_object(_RD)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return []

    def set_rect_differences(
        self, *differences: float | list[float] | None
    ) -> None:
        """Set ``/RD`` from per-side differences.

        Mirrors upstream's overloaded ``setRectDifferences``:

        * ``set_rect_differences(d)`` — apply ``d`` to all four sides.
        * ``set_rect_differences(left, top, right, bottom)`` — explicit per-side.
        * ``set_rect_differences([l, t, r, b])`` — Python-friendly list form.
        * ``set_rect_differences(None)`` — clear the entry.
        """
        if len(differences) == 1:
            difference = differences[0]
            if difference is None:
                self._dict.remove_item(_RD)
                return
            if isinstance(difference, list):
                values = [float(d) for d in difference]
                if len(values) != 4:
                    raise ValueError(
                        "set_rect_differences list form requires 4 values, "
                        f"got {len(values)}"
                    )
                self._dict.set_item(
                    _RD, COSArray([COSFloat(v) for v in values])
                )
                return
            value = float(difference)
            self._dict.set_item(
                _RD,
                COSArray([COSFloat(value)] * 4),
            )
            return

        if len(differences) == 4:
            values = [float(d) for d in differences]  # type: ignore[arg-type]
            self._dict.set_item(
                _RD, COSArray([COSFloat(v) for v in values])
            )
            return

        raise TypeError("set_rect_differences expects 1 or 4 values")


class PDAnnotationSquare(PDAnnotationSquareCircle):
    """``/Subtype /Square`` annotation."""

    SUB_TYPE: str = "Square"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        if annotation_dict is None:
            super().__init__(self.SUB_TYPE)
        elif not isinstance(annotation_dict, COSDictionary):
            raise TypeError(
                "PDAnnotationSquare requires a COSDictionary or None; got "
                f"{type(annotation_dict).__name__}"
            )
        else:
            super().__init__(annotation_dict)


class PDAnnotationCircle(PDAnnotationSquareCircle):
    """``/Subtype /Circle`` annotation."""

    SUB_TYPE: str = "Circle"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        if annotation_dict is None:
            super().__init__(self.SUB_TYPE)
        elif not isinstance(annotation_dict, COSDictionary):
            raise TypeError(
                "PDAnnotationCircle requires a COSDictionary or None; got "
                f"{type(annotation_dict).__name__}"
            )
        else:
            super().__init__(annotation_dict)


__all__ = [
    "PDAnnotationCircle",
    "PDAnnotationSquare",
    "PDAnnotationSquareCircle",
]

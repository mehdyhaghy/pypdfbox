from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_annotation import PDAnnotation

_BS: COSName = COSName.get_pdf_name("BS")
_IC: COSName = COSName.get_pdf_name("IC")
_BE: COSName = COSName.get_pdf_name("BE")


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

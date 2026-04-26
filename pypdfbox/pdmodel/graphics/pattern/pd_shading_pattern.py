from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_abstract_pattern import PDAbstractPattern

_PATTERN_TYPE: COSName = COSName.get_pdf_name("PatternType")
_SHADING: COSName = COSName.get_pdf_name("Shading")


class PDShadingPattern(PDAbstractPattern):
    """Shading pattern (``/PatternType 2``). Mirrors PDFBox
    ``PDShadingPattern`` lite surface.

    Lite: ``/Shading`` is exposed as the raw ``COSBase`` (a typed
    ``PDShading`` wrapper is delivered by a sibling cluster); the
    ``/ExtGState`` accessors inherited from ``PDAbstractPattern`` return
    the raw dictionary."""

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            # Fresh dict — set the fixed PatternType code. Upstream's
            # no-arg ctor sets only PatternType (Type/Pattern was set by
            # the abstract base init).
            self._dict.set_int(
                _PATTERN_TYPE, PDAbstractPattern.TYPE_SHADING_PATTERN
            )

    # ---------- /PatternType ----------

    def get_pattern_type(self) -> int:
        return PDAbstractPattern.TYPE_SHADING_PATTERN

    # ---------- /Shading ----------

    def get_shading(self) -> COSBase | None:
        """Raw ``/Shading`` entry — typically a ``COSDictionary`` (shading
        types 1–3) or a ``COSStream`` (shading types 4–7). The typed
        ``PDShading`` wrapper is delivered by a sibling cluster."""
        return self._dict.get_dictionary_object(_SHADING)

    def set_shading(self, shading: COSBase | None) -> None:
        if shading is None:
            self._dict.remove_item(_SHADING)
            return
        self._dict.set_item(_SHADING, shading)


__all__ = ["PDShadingPattern"]

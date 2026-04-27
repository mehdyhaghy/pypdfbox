from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_abstract_pattern import PDAbstractPattern

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading

_PATTERN_TYPE: COSName = COSName.get_pdf_name("PatternType")
_SHADING: COSName = COSName.get_pdf_name("Shading")


class PDShadingPattern(PDAbstractPattern):
    """Shading pattern (``/PatternType 2``). Mirrors PDFBox
    ``PDShadingPattern``.

    ``/Shading`` is exposed as a typed ``PDShading`` (dispatched on
    ``/ShadingType``); ``/Matrix`` and ``/ExtGState`` accessors are
    inherited from ``PDAbstractPattern`` (the ``ExtGState`` accessor on
    the base now also returns a typed ``PDExtendedGraphicsState``)."""

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

    def get_shading(self) -> PDShading | None:
        """Typed ``/Shading`` accessor — mirrors upstream
        ``PDShadingPattern.getShading``. Returns a ``PDShading`` subclass
        (dispatched on ``/ShadingType`` by ``PDShading.create``) or
        ``None`` when the entry is absent."""
        # Local import — avoids dragging the shading subclass tree into
        # the pattern module's import graph at load time.
        from pypdfbox.pdmodel.graphics.shading.pd_shading import (  # noqa: PLC0415
            PDShading as _PDShading,
        )

        value = self._dict.get_dictionary_object(_SHADING)
        if value is None:
            return None
        if not isinstance(value, COSDictionary):
            return None
        return _PDShading.create(value)

    def set_shading(self, shading: PDShading | COSBase | None) -> None:
        """Accepts a typed ``PDShading``, a raw ``COSBase`` (typically
        ``COSDictionary`` / ``COSStream``), or ``None`` (clears the
        entry)."""
        from pypdfbox.pdmodel.graphics.shading.pd_shading import (  # noqa: PLC0415
            PDShading as _PDShading,
        )

        if shading is None:
            self._dict.remove_item(_SHADING)
            return
        if isinstance(shading, _PDShading):
            self._dict.set_item(_SHADING, shading.get_cos_object())
            return
        if isinstance(shading, COSBase):
            self._dict.set_item(_SHADING, shading)
            return
        raise TypeError(
            "set_shading expects PDShading, COSBase, or None; got "
            f"{type(shading).__name__}"
        )


__all__ = ["PDShadingPattern"]

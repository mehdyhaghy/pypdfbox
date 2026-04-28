from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_abstract_pattern import PDAbstractPattern

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

_PATTERN_TYPE: COSName = COSName.get_pdf_name("PatternType")
_SHADING: COSName = COSName.get_pdf_name("Shading")
_EXT_G_STATE: COSName = COSName.get_pdf_name("ExtGState")


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

    # ---------- /ExtGState (typed override — upstream parity) ----------

    def get_extended_graphics_state(self) -> PDExtendedGraphicsState | None:
        """Typed ``/ExtGState`` accessor — mirrors upstream
        ``PDShadingPattern.getExtendedGraphicsState``. Returns a typed
        ``PDExtendedGraphicsState`` wrapper or ``None``.

        Note: the base ``PDAbstractPattern.get_extended_graphics_state``
        returns the raw ``COSDictionary`` for back-compat; on shading
        patterns we override to match upstream's typed return."""
        from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (  # noqa: PLC0415
            PDExtendedGraphicsState,
        )

        value = self._dict.get_dictionary_object(_EXT_G_STATE)
        if isinstance(value, COSDictionary):
            return PDExtendedGraphicsState(value)
        return None

    def set_extended_graphics_state(
        self, ext_g_state: PDExtendedGraphicsState | COSDictionary | None
    ) -> None:
        """Typed ``/ExtGState`` setter — mirrors upstream
        ``PDShadingPattern.setExtendedGraphicsState``."""
        from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (  # noqa: PLC0415
            PDExtendedGraphicsState,
        )

        if ext_g_state is None:
            self._dict.remove_item(_EXT_G_STATE)
            return
        if isinstance(ext_g_state, PDExtendedGraphicsState):
            self._dict.set_item(_EXT_G_STATE, ext_g_state.get_cos_object())
            return
        if isinstance(ext_g_state, COSDictionary):
            self._dict.set_item(_EXT_G_STATE, ext_g_state)
            return
        raise TypeError(
            "set_extended_graphics_state expects PDExtendedGraphicsState, "
            f"COSDictionary, or None; got {type(ext_g_state).__name__}"
        )

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

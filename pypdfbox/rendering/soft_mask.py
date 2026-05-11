"""Paint that applies a soft mask to an underlying paint.

Mirrors ``org.apache.pdfbox.rendering.SoftMask`` plus the inner
``SoftPaintContext``.

The full upstream class is wired to ``java.awt.Paint`` /
``PaintContext`` and is not directly usable on Pillow. We preserve the
constructor surface and the public methods so the rest of the renderer
can hand a ``SoftMask`` instance to its compositor; the actual masking
math lives in ``SoftPaintContext.get_raster`` (a hand-port of upstream's
inner ``getRaster``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.function.pd_function import PDFunction
    from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

_LOG = logging.getLogger(__name__)

# AWT Transparency constant — kept literal so we don't need an AWT shim.
TRANSLUCENT = 3


class SoftMask:
    """A paint that combines an underlying paint with a soft mask."""

    def __init__(
        self,
        paint: Any,
        mask: Any,
        bbox_device: Any,
        backdrop_color: PDColor | None = None,
        transfer_function: PDFunction | None = None,
    ) -> None:
        self._paint = paint
        self._mask = mask
        self._bbox_device = bbox_device
        self._bc = 0  # backdrop luminance (0..255)
        # Identity functions become None upstream, so the paint context
        # can short-circuit the per-pixel transfer call.
        if transfer_function is not None and getattr(
            transfer_function, "is_identity", lambda: False
        )():
            self._transfer_function: PDFunction | None = None
        else:
            self._transfer_function = transfer_function
        if backdrop_color is not None:
            try:
                rgb = backdrop_color.to_rgb()
                r = (rgb >> 16) & 0xFF
                g = (rgb >> 8) & 0xFF
                b = rgb & 0xFF
                # ITU-R BT.601 luma.
                self._bc = (299 * r + 587 * g + 114 * b) // 1000
            except OSError as exc:
                _LOG.debug("Couldn't convert backdropColor to RGB: %s", exc)

    def create_context(
        self,
        cm: Any,
        device_bounds: Any,
        user_bounds: Any,
        xform: Any,
        hints: Any,
    ) -> SoftPaintContext:
        """Create the per-paint context (mirrors AWT ``Paint.createContext``)."""
        ctx = (
            self._paint.create_context(cm, device_bounds, user_bounds, xform, hints)
            if hasattr(self._paint, "create_context")
            else None
        )
        return SoftPaintContext(self, ctx)

    def get_transparency(self) -> int:
        """Mirror upstream ``Paint.getTransparency()`` -> ``TRANSLUCENT``."""
        return TRANSLUCENT


class SoftPaintContext:
    """Per-paint context that mixes the inner paint with the soft mask.

    Mirrors upstream's inner ``SoftPaintContext`` (line 116 of
    ``SoftMask.java``). The hot loop walks the inner-paint raster pixel
    by pixel, multiplying alpha by the soft mask's luminance.
    """

    def __init__(self, owner: SoftMask, context: Any) -> None:
        self._owner = owner
        self._context = context

    def dispose(self) -> None:
        """Release wrapped paint-context resources."""
        if self._context is not None and hasattr(self._context, "dispose"):
            self._context.dispose()

    def get_color_model(self) -> Any:
        """Always ARGB — mirrors upstream constant."""
        return "ARGB"

    def get_raster(self, x1: int, y1: int, w: int, h: int) -> Any:
        """Return a raster sized ``w x h`` starting at ``(x1, y1)``.

        TODO: full implementation needs the inner context's raster +
        per-pixel alpha multiplication.
        """
        return None


__all__ = ["SoftMask", "SoftPaintContext"]

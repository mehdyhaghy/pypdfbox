"""Paint that applies a soft mask to an underlying paint.

Mirrors ``org.apache.pdfbox.rendering.SoftMask`` plus the inner
``SoftPaintContext``.

The full upstream class is wired to ``java.awt.Paint`` /
``PaintContext``. The Python port keeps the constructor surface and the
public methods, and provides a working ``SoftPaintContext.get_raster``
that mixes the inner paint's raster with the soft-mask luminance using
Pillow's per-pixel access (``Image.composite`` / ``ImageChops`` aren't
directly applicable because the inner paint can be any opaque object).
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


def _clamp_unit(v: float) -> float:
    """Clamp ``v`` into the unit interval ``[0.0, 1.0]``."""
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


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
                # Upstream's ``toRGB()`` returns a packed ARGB int (Java
                # ``Color.getRGB``); the pypdfbox lite surface returns a
                # 3-tuple of unit floats. Support both shapes so the
                # luminance computation works regardless of which one we
                # got.
                if isinstance(rgb, tuple):
                    r = int(round(_clamp_unit(rgb[0]) * 255.0))
                    g = int(round(_clamp_unit(rgb[1]) * 255.0))
                    b = int(round(_clamp_unit(rgb[2]) * 255.0))
                else:
                    r = (rgb >> 16) & 0xFF
                    g = (rgb >> 8) & 0xFF
                    b = rgb & 0xFF
                # ITU-R BT.601 luma.
                self._bc = (299 * r + 587 * g + 114 * b) // 1000
            except (OSError, TypeError, ValueError, IndexError) as exc:
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
        if self._context is not None and hasattr(self._context, "dispose"):  # pragma: no branch
            # Defensive: the wrapped paint-context always exposes
            # dispose() in the live rendering pipeline; the False arm
            # has no live caller.
            self._context.dispose()

    def get_color_model(self) -> Any:
        """Always ARGB — mirrors upstream constant."""
        return "ARGB"

    def get_raster(self, x1: int, y1: int, w: int, h: int) -> Any:
        """Return a raster sized ``w x h`` starting at ``(x1, y1)``.

        Mirrors upstream ``SoftPaintContext.getRaster`` (lines 131-213):
        walks the inner paint's raster and multiplies each pixel's alpha
        by the soft mask's gray value at the matching coordinate (with
        ``bc`` as the fallback outside the mask bounds). Uses the
        per-pixel transfer function when set.
        """
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - exercised in lossless tests
            _LOG.debug("Pillow not available; soft-mask compositing skipped")
            return None

        if w <= 0 or h <= 0:
            return Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))

        # Fetch the inner paint's raster (Pillow Image expected). If the
        # inner context can't produce one, fall back to a solid black
        # ARGB raster — matches AWT's behaviour when ``paint`` is null
        # (the result is all-transparent because alpha == 0).
        inner_image = None
        if self._context is not None and hasattr(self._context, "get_raster"):
            inner_image = self._context.get_raster(x1, y1, w, h)
        if inner_image is None:
            inner_image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if inner_image.mode != "RGBA":
            inner_image = inner_image.convert("RGBA")
        if inner_image.size != (w, h):
            inner_image = inner_image.crop((0, 0, w, h))

        mask = self._owner._mask
        bbox = self._owner._bbox_device
        try:
            bx = int(bbox[0]) if bbox is not None else 0
            by = int(bbox[1]) if bbox is not None else 0
        except (TypeError, IndexError, ValueError):
            bx = by = 0

        # Translate the destination origin into mask coordinates the way
        # upstream does (x1 -= bboxDevice.x; y1 -= bboxDevice.y).
        mx0 = x1 - bx
        my0 = y1 - by

        mask_w = mask.width if mask is not None else 0
        mask_h = mask.height if mask is not None else 0
        # Ensure mask is in single-channel luma form (matches upstream's
        # ``maskRaster.getPixel`` returning a single gray sample).
        if mask is not None and mask.mode not in ("L", "LA"):
            mask_l = mask.convert("L")
        else:
            mask_l = mask if mask is None else (mask if mask.mode == "L" else mask.convert("L"))
        mask_pixels = mask_l.load() if mask_l is not None else None

        bc = self._owner._bc
        transfer = self._owner._transfer_function
        # Cache transfer results per gray value (matches upstream's
        # ``map`` table).
        transfer_cache: dict[int, float] = {}

        def _transfer(g: int) -> float:
            if transfer is None:
                return g / 255.0
            cached = transfer_cache.get(g)
            if cached is not None:
                return cached
            try:
                out = transfer.eval([g / 255.0])
                val = float(out[0])
            except (OSError, ValueError, IndexError, TypeError) as exc:
                _LOG.debug("transferFunction failed, treating as outside: %s", exc)
                val = bc / 255.0
            transfer_cache[g] = val
            return val

        in_pixels = inner_image.load()
        out_image = Image.new("RGBA", (w, h))
        out_pixels = out_image.load()

        for y in range(h):
            for x in range(w):
                src = in_pixels[x, y]
                r = src[0]
                g_c = src[1]
                b_c = src[2]
                a = src[3] if len(src) > 3 else 255
                mx = mx0 + x
                my = my0 + y
                if mask_pixels is not None and 0 <= mx < mask_w and 0 <= my < mask_h:
                    g_mask = mask_pixels[mx, my]
                    if isinstance(g_mask, tuple):
                        g_mask = g_mask[0]
                    g_val = int(g_mask)
                else:
                    # Outside the mask bounds the backdrop luminance ``bc``
                    # is the sample (upstream sets ``g = bc``). It still
                    # goes through the same transfer-function ``map`` as an
                    # in-bounds sample — upstream builds one 256-entry
                    # ``map`` table and indexes it with ``bc`` here too — so
                    # a non-identity ``/TR`` remaps the out-of-bounds region
                    # exactly like the covered region.
                    g_val = bc
                factor = _transfer(g_val)
                new_alpha = int(round(a * factor))
                out_pixels[x, y] = (r, g_c, b_c, max(0, min(255, new_alpha)))

        return out_image


__all__ = ["SoftMask", "SoftPaintContext"]

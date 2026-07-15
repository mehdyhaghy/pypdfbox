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

        import numpy as np  # noqa: PLC0415

        # Vectorised equivalent of the former per-pixel loop. The RGB
        # bands pass through untouched; only the alpha band is scaled by
        # the transfer-mapped mask sample.
        inner_arr = np.asarray(inner_image)  # (h, w, 4) uint8, RGBA

        # Per-pixel mask sample ``g_val``. Default is the backdrop
        # luminance ``bc`` (out-of-mask-bounds regions); in-bounds pixels
        # take the mask's gray sample. Out-of-bounds pixels still go
        # through the same transfer ``map`` as in-bounds ones.
        g_val = np.full((h, w), bc, dtype=np.int64)
        if mask_pixels is not None and mask_w > 0 and mask_h > 0:
            mask_arr = np.asarray(mask_l)  # (mask_h, mask_w[, bands]) uint8
            if mask_arr.ndim == 3:
                # LA / multi-band mask: sample the first (luma) band,
                # mirroring the former ``g_mask[0]`` tuple unwrap.
                mask_arr = mask_arr[:, :, 0]
            xs = mx0 + np.arange(w)
            ys = my0 + np.arange(h)
            vx = (xs >= 0) & (xs < mask_w)
            vy = (ys >= 0) & (ys < mask_h)
            if vx.any() and vy.any():
                iy = np.nonzero(vy)[0]
                ix = np.nonzero(vx)[0]
                g_val[np.ix_(iy, ix)] = mask_arr[
                    np.ix_(ys[vy], xs[vx])
                ].astype(np.int64)

        # Build a 256-entry factor LUT, evaluating ``_transfer`` only for
        # the gray values actually present (mirrors the loop's per-value
        # ``transfer_cache``; results are identical regardless of order).
        factor_lut = np.zeros(256, dtype=np.float64)
        for gv in np.unique(g_val).tolist():
            factor_lut[gv] = _transfer(int(gv))
        factor_grid = factor_lut[g_val]

        a = inner_arr[:, :, 3].astype(np.float64)
        new_alpha = np.clip(np.rint(a * factor_grid), 0, 255).astype(np.uint8)
        out_arr = inner_arr.copy()
        out_arr[:, :, 3] = new_alpha
        return Image.fromarray(out_arr, "RGBA")


__all__ = ["SoftMask", "SoftPaintContext"]

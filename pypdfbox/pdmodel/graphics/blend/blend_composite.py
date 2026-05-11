"""AWT-compatible composite for blend modes.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.blend.BlendComposite``.

Upstream wires this into ``java.awt.Composite`` so AWT's painting
pipeline applies the blend equation when a non-normal blend mode is
active. The Python port keeps the same shape so callers porting from
PDFBox can find the API in the expected location; the actual pixel
mixing is done lazily and operates on plain float arrays (no AWT).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

_LOG = logging.getLogger(__name__)


class BlendComposite:
    """A composite that blends two pixels using a PDF blend mode."""

    __slots__ = ("blend_mode", "constant_alpha")

    def __init__(self, blend_mode: BlendMode, constant_alpha: float) -> None:
        self.blend_mode = blend_mode
        self.constant_alpha = float(constant_alpha)

    @staticmethod
    def get_instance(blend_mode: BlendMode | None, constant_alpha: float) -> Any:
        """Mirror ``BlendComposite.getInstance(BlendMode, float)``.

        Upstream returns ``AlphaComposite.SRC_OVER`` for ``NORMAL`` and a
        ``BlendComposite`` for everything else. Python has no AWT, so we
        return a sentinel for the SRC_OVER case (a tuple) which callers
        can recognise; in practice the renderer only consults the
        ``blend_mode`` attribute.
        """
        if constant_alpha < 0:
            _LOG.warning("using 0 instead of incorrect Alpha %s", constant_alpha)
            constant_alpha = 0.0
        elif constant_alpha > 1:
            _LOG.warning("using 1 instead of incorrect Alpha %s", constant_alpha)
            constant_alpha = 1.0
        if blend_mode is None:
            raise ValueError("blendMode parameter cannot be null")
        if blend_mode is BlendMode.NORMAL:
            return ("AlphaComposite.SRC_OVER", constant_alpha)
        return BlendComposite(blend_mode, constant_alpha)

    def create_context(
        self,
        src_color_model: Any,
        dst_color_model: Any,
        hints: Any | None = None,
    ) -> BlendCompositeContext:
        """Create the composite's per-painting context."""
        return BlendCompositeContext(self, src_color_model, dst_color_model)


class BlendCompositeContext:
    """The per-painting context that does the actual pixel blending.

    Inner class of upstream's ``BlendComposite`` (line 93 of
    ``BlendComposite.java``). Carries source/destination colour models
    and runs the channel blend over a rectangle.
    """

    __slots__ = ("_owner", "src_color_model", "dst_color_model")

    def __init__(
        self,
        owner: BlendComposite,
        src_color_model: Any,
        dst_color_model: Any,
    ) -> None:
        self._owner = owner
        self.src_color_model = src_color_model
        self.dst_color_model = dst_color_model

    def dispose(self) -> None:
        """Upstream contract: release resources. Nothing needed in Python."""

    def compose(
        self,
        src: Sequence[Sequence[float]],
        dst_in: Sequence[Sequence[float]],
        dst_out: list[list[float]],
    ) -> None:
        """Blend ``src`` over ``dst_in``, writing into ``dst_out``.

        Hand-port of the inner ``compose(Raster, Raster, WritableRaster)``
        from upstream. Inputs are 2D arrays of pixel component lists
        (RGB or RGBA), already normalised to ``[0, 1]``.
        """
        mode = self._owner.blend_mode
        ca = self._owner.constant_alpha
        is_separable = bool(getattr(mode, "is_separable_blend_mode", lambda: True)())
        height = min(len(src), len(dst_in), len(dst_out))
        width = min(
            min(len(src[0]), len(dst_in[0])) if height else 0,
            len(dst_out[0]) if height else 0,
        )
        for y in range(height):
            for x in range(width):
                s = list(src[y][x])
                d = list(dst_in[y][x])
                # Decompose alpha.
                src_alpha = s[3] if len(s) > 3 else 1.0
                dst_alpha = d[3] if len(d) > 3 else 1.0
                src_alpha *= ca
                result_alpha = dst_alpha + src_alpha - src_alpha * dst_alpha
                src_alpha_ratio = (src_alpha / result_alpha) if result_alpha > 0 else 0.0

                if is_separable:
                    fn = getattr(mode, "get_blend_channel_function", lambda: None)()
                    if fn is None:
                        fn = lambda a, b: a  # noqa: E731 - normal fallback
                    out = []
                    for k in range(3):
                        sv = s[k]
                        dv = d[k]
                        v = fn(sv, dv) if callable(fn) else fn.blend_channel(sv, dv)
                        v = sv + dst_alpha * (v - sv)
                        v = dv + src_alpha_ratio * (v - dv)
                        out.append(v)
                else:
                    fn = getattr(mode, "get_blend_function", lambda: None)()
                    rgb_result = [0.0, 0.0, 0.0]
                    if fn is not None:
                        if callable(fn):
                            fn(s[:3], d[:3], rgb_result)
                        else:
                            fn.blend(s[:3], d[:3], rgb_result)
                    out = []
                    for k in range(3):
                        sv = s[k]
                        dv = d[k]
                        v = max(0.0, min(1.0, rgb_result[k]))
                        v = sv + dst_alpha * (v - sv)
                        v = dv + src_alpha_ratio * (v - dv)
                        out.append(v)
                if len(d) > 3:
                    out.append(result_alpha)
                dst_out[y][x] = out


__all__ = ["BlendComposite", "BlendCompositeContext"]

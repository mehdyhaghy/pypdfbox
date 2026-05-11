"""Abstract base for AWT-style shading paint contexts.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.ShadingContext``.

In pypdfbox we don't bind to ``java.awt.PaintContext``; instead a context
exposes :py:meth:`get_raster` returning a ``PIL.Image.Image`` patch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .pd_shading import PDShading


class ShadingContext:
    """Base class encapsulating background / colour-space conversion logic."""

    def __init__(
        self,
        shading: PDShading,
        color_model: Any,
        xform: Any,
        matrix: Any,
    ) -> None:
        self._shading = shading
        self._shading_color_space = shading.get_color_space()
        self._output_color_model = color_model
        self._background: list[float] | None = None
        self._rgb_background: int = 0
        bg = shading.get_background()
        if bg is not None:
            self._background = list(bg.to_float_array())
            self._rgb_background = self.convert_to_rgb(self._background)

    # ------------------------------------------------------------------
    # Accessors mirroring upstream package-private getters
    # ------------------------------------------------------------------
    def get_shading_color_space(self) -> Any:
        return self._shading_color_space

    def get_shading(self) -> PDShading:
        return self._shading

    def get_background(self) -> list[float] | None:
        return self._background

    def get_rgb_background(self) -> int:
        return self._rgb_background

    def get_color_model(self) -> Any:
        return self._output_color_model

    # ------------------------------------------------------------------
    # Conversions
    # ------------------------------------------------------------------
    def convert_to_rgb(self, values: list[float]) -> int:
        """Convert shading-space colour values to a packed RGB int."""
        cs = self._shading_color_space
        if cs is None or not hasattr(cs, "to_rgb"):
            # Treat the values as already in 0..1 RGB.
            rgb = list(values) + [0.0, 0.0, 0.0]
        else:
            try:
                rgb = list(cs.to_rgb(values))
            except (TypeError, NotImplementedError):
                rgb = list(values) + [0.0, 0.0, 0.0]
        r = int(max(0.0, min(1.0, rgb[0])) * 255)
        g = int(max(0.0, min(1.0, rgb[1])) * 255)
        b = int(max(0.0, min(1.0, rgb[2])) * 255)
        return r | (g << 8) | (b << 16)

    def dispose(self) -> None:
        self._output_color_model = None
        self._shading_color_space = None

    # ------------------------------------------------------------------
    # Abstract raster API – subclasses must override.
    # ------------------------------------------------------------------
    def get_raster(self, x: int, y: int, w: int, h: int) -> Any:
        """Abstract — subclasses produce a ``PIL.Image`` (RGBA) covering
        the region ``(x, y, w, h)`` in device space. Mirrors upstream
        ``ShadingContext.getRaster`` which is implemented per subclass."""
        _ = (x, y, w, h)
        raise NotImplementedError(
            "ShadingContext.get_raster is abstract; override in a subclass"
        )

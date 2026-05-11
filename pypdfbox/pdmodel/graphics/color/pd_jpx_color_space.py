"""JPX embedded color space.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.color.PDJPXColorSpace``.

Wraps the AWT ``ColorSpace`` obtained after JAI ImageIO reads a JPX stream.
Python port: callers pass a Pillow ``ImageCms``-style profile or any object
exposing ``get_num_components()`` / ``to_rgb()`` / ``get_min_value`` /
``get_max_value`` (we only invoke methods upstream invokes).
"""

from __future__ import annotations

from typing import Any

from .pd_color import PDColor
from .pd_color_space import PDColorSpace


class PDJPXColorSpace(PDColorSpace):
    """A color space embedded in a JPX file."""

    def __init__(self, color_space: Any) -> None:
        super().__init__()
        self._awt_color_space = color_space

    def get_name(self) -> str:
        """Return the fixed name ``"JPX"``."""
        return "JPX"

    def get_number_of_components(self) -> int:
        """Return the underlying color space's component count."""
        if hasattr(self._awt_color_space, "get_num_components"):
            return int(self._awt_color_space.get_num_components())
        if hasattr(self._awt_color_space, "num_components"):
            return int(self._awt_color_space.num_components)
        return 3

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Return a 2N-length decode array using AWT min/max accessors."""
        n = self.get_number_of_components()
        decode: list[float] = []
        for i in range(n):
            if hasattr(self._awt_color_space, "get_min_value"):
                lo = float(self._awt_color_space.get_min_value(i))
                hi = float(self._awt_color_space.get_max_value(i))
            else:
                lo, hi = 0.0, 1.0
            decode.append(lo)
            decode.append(hi)
        return decode

    def get_initial_color(self) -> PDColor:
        """Upstream raises ``UnsupportedOperationException``."""
        raise NotImplementedError("JPX color spaces don't support drawing")

    def to_rgb(self, value: list[float]) -> list[float]:
        """Delegate to the wrapped color space's ``toRGB``."""
        if hasattr(self._awt_color_space, "to_rgb"):
            return list(self._awt_color_space.to_rgb(value))
        return list(value[:3])

    def to_rgb_image(self, raster: Any) -> Any:
        """Build an sRGB image by walking pixels through ``to_rgb``."""
        try:
            from PIL import Image
        except ImportError:
            return None
        width = raster.get_width()
        height = raster.get_height()
        out = Image.new("RGB", (width, height))
        pixels = out.load()
        n = self.get_number_of_components()
        for y in range(height):
            for x in range(width):
                px = list(raster.get_pixel(x, y, [0.0] * n))
                rgb = self.to_rgb([v / 255.0 for v in px])
                pixels[x, y] = (
                    int(max(0.0, min(255.0, rgb[0] * 255))),
                    int(max(0.0, min(255.0, rgb[1] * 255))),
                    int(max(0.0, min(255.0, rgb[2] * 255))),
                )
        return out

    def to_raw_image(self, raster: Any) -> Any:
        """Return the raster as-is in the underlying color space."""
        return raster

    def get_cos_object(self) -> Any:
        """Upstream raises ``UnsupportedOperationException``."""
        raise NotImplementedError("JPX color spaces don't have COS objects")


__all__ = ["PDJPXColorSpace"]

"""Abstract base for CIE-based colour spaces.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.color.PDCIEBasedColorSpace``.

CIE-based colour spaces specify colours in a way that is independent of the
characteristics of any particular output device. They are based on the
Commission Internationale de l'Eclairage standards.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from .pd_color_space import PDColorSpace


class PDCIEBasedColorSpace(PDColorSpace):
    """Abstract parent for CalGray / CalRGB / Lab / ICCBased."""

    @abstractmethod
    def to_rgb(self, value: list[float]) -> list[float]:
        """Convert a single colour sample to sRGB. Subclass-supplied."""

    def to_rgb_image(self, raster: Any) -> Any:
        """Convert a single-pixel-style raster to an sRGB image.

        Mirrors upstream ``toRGBImage(WritableRaster)``: walks every pixel,
        normalises 0..255 to 0..1, calls ``toRGB``, then expands back.

        The raster is expected to expose ``get_width()``, ``get_height()``,
        ``get_pixel(x, y, abc)`` and a result image with ``get_raster()`` /
        ``set_pixel``. This mirrors the AWT contract; callers wiring this
        up to Pillow provide a thin adapter.
        """
        if raster is None:
            return None
        width = raster.get_width()
        height = raster.get_height()
        try:
            from PIL import Image
        except ImportError:
            return None
        rgb_image = Image.new("RGB", (width, height))
        pixels = rgb_image.load()
        for y in range(height):
            for x in range(width):
                abc = list(raster.get_pixel(x, y, [0.0, 0.0, 0.0]))
                abc[0] /= 255.0
                abc[1] /= 255.0
                abc[2] /= 255.0
                rgb = self.to_rgb(abc)
                pixels[x, y] = (
                    int(max(0.0, min(255.0, rgb[0] * 255))),
                    int(max(0.0, min(255.0, rgb[1] * 255))),
                    int(max(0.0, min(255.0, rgb[2] * 255))),
                )
        return rgb_image

    def to_raw_image(self, raster: Any) -> Any:
        """No direct CIE equivalent in PIL; mirror upstream's ``return null``."""
        return None

    def to_string(self) -> str:
        """Mirror upstream ``toString()``."""
        return self.get_name()

    @abstractmethod
    def get_name(self) -> str:  # pragma: no cover - abstract reminder
        ...

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["PDCIEBasedColorSpace"]

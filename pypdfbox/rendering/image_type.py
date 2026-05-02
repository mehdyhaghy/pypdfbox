"""Image type for rendering.

Mirrors ``org.apache.pdfbox.rendering.ImageType``. Upstream models the
five Java BufferedImage flavours (BINARY / GRAY / RGB / ARGB / BGR) as
an enum where each value implements ``toBufferedImageType()`` returning
the matching ``BufferedImage.TYPE_*`` int constant.

Pillow has no direct equivalent of those Java AWT type constants. We
preserve the upstream API shape — ``ImageType.RGB.to_buffered_image_type()``
returns the same int the Java enum does — so downstream tooling porting
from PDFBox doesn't blow up on AttributeError. The lite renderer in
:mod:`pypdfbox.rendering.pdf_renderer` reads the ``pil_mode`` property
to pick the matching Pillow ``Image.new(mode=...)`` argument.
"""

from __future__ import annotations

from enum import Enum

# AWT BufferedImage type constants (java.awt.image.BufferedImage). Kept
# as module-level ints so callers porting from upstream Java code can
# compare against the same values without us re-deriving the magic
# numbers in a dozen places.
TYPE_INT_RGB: int = 1
TYPE_INT_ARGB: int = 2
TYPE_3BYTE_BGR: int = 5
TYPE_BYTE_GRAY: int = 10
TYPE_BYTE_BINARY: int = 12


class ImageType(Enum):
    """Image type for rendering."""

    # Black or white.
    BINARY = "BINARY"
    # Shades of gray.
    GRAY = "GRAY"
    # Red, Green, Blue.
    RGB = "RGB"
    # Alpha, Red, Green, Blue.
    ARGB = "ARGB"
    # Blue, Green, Red.
    BGR = "BGR"

    def to_buffered_image_type(self) -> int:
        """Return the matching ``java.awt.image.BufferedImage.TYPE_*``
        integer constant. Mirrors upstream ``toBufferedImageType()``.
        """
        return _AWT_TYPE_BY_NAME[self.name]

    @property
    def pil_mode(self) -> str:
        """Pillow ``Image.new(mode=...)`` value for this image type.

        Pillow doesn't have a packed BGR mode; we collapse BGR back to
        ``"RGB"`` and rely on the renderer to swap channels at the
        boundary if a caller specifically wants BGR pixel order.
        """
        return _PIL_MODE_BY_NAME[self.name]


_AWT_TYPE_BY_NAME: dict[str, int] = {
    "BINARY": TYPE_BYTE_BINARY,
    "GRAY": TYPE_BYTE_GRAY,
    "RGB": TYPE_INT_RGB,
    "ARGB": TYPE_INT_ARGB,
    "BGR": TYPE_3BYTE_BGR,
}

_PIL_MODE_BY_NAME: dict[str, str] = {
    "BINARY": "1",
    "GRAY": "L",
    "RGB": "RGB",
    "ARGB": "RGBA",
    "BGR": "RGB",
}


__all__ = [
    "TYPE_3BYTE_BGR",
    "TYPE_BYTE_BINARY",
    "TYPE_BYTE_GRAY",
    "TYPE_INT_ARGB",
    "TYPE_INT_RGB",
    "ImageType",
]

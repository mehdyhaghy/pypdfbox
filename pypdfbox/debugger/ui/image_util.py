"""Utility helpers for image manipulation in the debugger.

Ported from ``org.apache.pdfbox.debugger.ui.ImageUtil``. The Java upstream
draws a ``BufferedImage`` onto a new ``Graphics2D`` and uses
``g.rotate(...)``; in Python we delegate to Pillow's ``Image.rotate`` /
``Image.transpose``, which are functionally equivalent for the multiples of
90 degrees that this helper accepts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image as PilImage


class ImageUtil:
    """Utility class for images.

    Instances cannot be created; all helpers are class methods, matching the
    final/private-constructor idiom upstream.
    """

    def __init__(self) -> None:  # pragma: no cover - mirrors ``private ImageUtil()``
        raise TypeError("ImageUtil is a static utility class")

    @staticmethod
    def get_rotated_image(image: PilImage, rotation: int) -> PilImage:
        """Return ``image`` rotated by ``rotation`` degrees (a multiple of 90).

        :raises ValueError: when ``rotation`` is not a multiple of 90.
        """
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - dependency declared in pyproject
            raise RuntimeError(
                "Pillow (PIL) is required for ImageUtil.get_rotated_image"
            ) from exc

        normalized = (rotation + 360) % 360
        if normalized == 0:
            return image
        if normalized == 90:
            return image.transpose(Image.ROTATE_270)
        if normalized == 180:
            return image.transpose(Image.ROTATE_180)
        if normalized == 270:
            return image.transpose(Image.ROTATE_90)
        raise ValueError("Only multiple of 90 are supported")

"""Image codec helpers, mirrors ``org.apache.pdfbox.tools.imageio``.

Ports:

- :class:`ImageIOUtil` (image_io_util.py)
- :class:`JPEGUtil`    (jpeg_util.py)
- :class:`MetaUtil`    (meta_util.py)
- :class:`TIFFUtil`    (tiff_util.py)

Library-first: Pillow handles JPEG/PNG/TIFF/GIF/BMP via
``PIL.Image.save``; we wrap that surface with PDFBox-shaped helpers.
"""
from __future__ import annotations

from .image_io_util import ImageIOUtil
from .jpeg_util import JPEGUtil
from .meta_util import MetaUtil
from .tiff_util import TIFFUtil

__all__ = ["ImageIOUtil", "JPEGUtil", "MetaUtil", "TIFFUtil"]

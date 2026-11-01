"""Image codec helpers, mirrors ``org.apache.pdfbox.tools.imageio``.

Ports:

- :class:`ImageIOUtil` (image_io_util.py)
- :class:`JPEGUtil`    (jpeg_util.py)
- :class:`MetaUtil`    (meta_util.py)
- :class:`TIFFUtil`    (tiff_util.py)

Library-first: Pillow handles JPEG/PNG/TIFF/GIF/BMP via
``PIL.Image.save``; we wrap that surface with PDFBox-shaped helpers.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .image_io_util import ImageIOUtil
    from .jpeg_util import JPEGUtil
    from .meta_util import MetaUtil
    from .tiff_util import TIFFUtil

__getattr__, __dir__ = _attach(
    __name__,
    {
        "ImageIOUtil": ".image_io_util",
        "JPEGUtil": ".jpeg_util",
        "MetaUtil": ".meta_util",
        "TIFFUtil": ".tiff_util",
    },
)

__all__ = ["ImageIOUtil", "JPEGUtil", "MetaUtil", "TIFFUtil"]

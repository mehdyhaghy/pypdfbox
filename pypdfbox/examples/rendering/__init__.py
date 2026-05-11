"""Port of ``org.apache.pdfbox.examples.rendering``.

Shows how to subclass :class:`pypdfbox.rendering.PDFRenderer` /
:class:`pypdfbox.rendering.PageDrawer` and how to drive
:class:`pypdfbox.contentstream.PDFGraphicsStreamEngine` for custom
processing. Image output is delegated to Pillow (already a transitive
dependency through the rendering module).
"""

from pypdfbox.examples.rendering.custom_graphics_stream_engine import (
    CustomGraphicsStreamEngine,
)
from pypdfbox.examples.rendering.custom_page_drawer import (
    CustomPageDrawer,
    MyPageDrawer,
    MyPDFRenderer,
)

__all__ = [
    "CustomGraphicsStreamEngine",
    "CustomPageDrawer",
    "MyPDFRenderer",
    "MyPageDrawer",
]

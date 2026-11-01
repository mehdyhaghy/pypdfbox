"""Tkinter port of ``org.apache.pdfbox.debugger.pagepane``.

Renders a PDF page using :class:`pypdfbox.rendering.PDFRenderer` and lets
the debugger UI overlay text-extraction debug info on top. The Swing
``JLabel`` + ``BufferedImage`` painting pipeline becomes a
``tk.Canvas`` (or ``ttk.Label``) with a ``PIL.ImageTk.PhotoImage``;
``Graphics2D.draw(Rectangle2D)`` overlays are drawn on the PIL side via
:class:`PIL.ImageDraw.ImageDraw` so we don't need a vector canvas.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .debug_text_overlay import DebugTextOverlay
    from .page_pane import PagePane

__getattr__, __dir__ = _attach(
    __name__,
    {
        "DebugTextOverlay": ".debug_text_overlay",
        "PagePane": ".page_pane",
    },
)

__all__ = ["DebugTextOverlay", "PagePane"]

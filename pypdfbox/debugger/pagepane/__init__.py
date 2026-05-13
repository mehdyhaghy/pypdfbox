"""Tkinter port of ``org.apache.pdfbox.debugger.pagepane``.

Renders a PDF page using :class:`pypdfbox.rendering.PDFRenderer` and lets
the debugger UI overlay text-extraction debug info on top. The Swing
``JLabel`` + ``BufferedImage`` painting pipeline becomes a
``tk.Canvas`` (or ``ttk.Label``) with a ``PIL.ImageTk.PhotoImage``;
``Graphics2D.draw(Rectangle2D)`` overlays are drawn on the PIL side via
:class:`PIL.ImageDraw.ImageDraw` so we don't need a vector canvas.
"""

from __future__ import annotations

from .debug_text_overlay import DebugTextOverlay
from .page_pane import PagePane

__all__ = ["DebugTextOverlay", "PagePane"]

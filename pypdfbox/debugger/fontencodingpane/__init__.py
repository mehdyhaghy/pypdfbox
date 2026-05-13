"""Tkinter port of ``org.apache.pdfbox.debugger.fontencodingpane``.

Dispatches a PDFont to the right encoding-inspector pane (Simple / Type0 /
Type3) and renders glyph thumbnails next to their PostScript name and
Unicode mapping. Mirrors the upstream Swing widget set 1:1.
"""

from __future__ import annotations

from pypdfbox.debugger.fontencodingpane.font_encoding_pane_controller import (
    FontEncodingPaneController,
)
from pypdfbox.debugger.fontencodingpane.font_encoding_view import FontEncodingView
from pypdfbox.debugger.fontencodingpane.font_pane import FontPane
from pypdfbox.debugger.fontencodingpane.simple_font import SimpleFont
from pypdfbox.debugger.fontencodingpane.type0_font import Type0Font
from pypdfbox.debugger.fontencodingpane.type3_font import Type3Font

__all__ = [
    "FontEncodingPaneController",
    "FontEncodingView",
    "FontPane",
    "SimpleFont",
    "Type0Font",
    "Type3Font",
]

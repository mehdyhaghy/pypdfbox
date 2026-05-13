"""Tkinter port of ``org.apache.pdfbox.debugger.stringpane``.

Hosts the :class:`StringPane` widget which renders a ``COSString``
side-by-side with its raw bytes (hex view).
"""

from __future__ import annotations

from pypdfbox.debugger.stringpane.string_pane import StringPane

__all__ = ["StringPane"]

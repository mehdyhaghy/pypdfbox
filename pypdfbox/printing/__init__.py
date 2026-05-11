"""Printing helpers ported from ``org.apache.pdfbox.printing``.

PDFBox uses Java AWT's ``Pageable`` / ``Printable`` interfaces. Python has
no standard equivalent, so :class:`PDFPageable` and :class:`PDFPrintable`
expose a callable surface that wraps :class:`PDFRenderer` and lets callers
plug into Pillow-based or platform-specific print backends. The shape of
the API mirrors PDFBox so user-facing code stays familiar.
"""

from __future__ import annotations

from pypdfbox.printing.pdf_pageable import PDFPageable
from pypdfbox.printing.pdf_printable import PDFPrintable

__all__ = ["PDFPageable", "PDFPrintable"]

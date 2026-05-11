"""Document-level printing bridge.

Mirrors ``org.apache.pdfbox.printing.PDFPageable`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/printing/PDFPageable.java``).

The Java class extends ``java.awt.print.Book``. Python's :mod:`platform`
print toolchain (CUPS / Win32 spooler) is out of scope; this port keeps
the API surface so callers can interrogate page count, page sizes and a
per-page :class:`PDFPrintable`.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pypdfbox.printing.pdf_printable import PDFPrintable

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


class Orientation(Enum):
    AUTO = "AUTO"
    PORTRAIT = "PORTRAIT"
    LANDSCAPE = "LANDSCAPE"


class PDFPageable:
    """Per-document driver that produces a :class:`PDFPrintable` per page."""

    def __init__(
        self,
        document: PDDocument,
        orientation: Orientation = Orientation.AUTO,
        show_page_border: bool = False,
        dpi: float = 0.0,
        center: bool = True,
    ) -> None:
        self._document = document
        self._orientation = orientation
        self._show_page_border = show_page_border
        self._dpi = dpi
        self._center = center
        self._subsampling_allowed = False
        self._rendering_hints: dict | None = None
        self._number_of_pages = document.get_number_of_pages()

    def get_rendering_hints(self) -> dict | None:
        return self._rendering_hints

    def set_rendering_hints(self, rendering_hints: dict | None) -> None:
        self._rendering_hints = rendering_hints

    def is_subsampling_allowed(self) -> bool:
        return self._subsampling_allowed

    def set_subsampling_allowed(self, subsampling_allowed: bool) -> None:
        self._subsampling_allowed = subsampling_allowed

    def get_number_of_pages(self) -> int:
        return self._number_of_pages

    def get_page_format(self, page_index: int) -> dict:
        """Return a paper-size descriptor for page ``page_index``."""
        page = self._document.get_page(page_index)
        media = page.get_media_box()
        return {
            "width": media.get_width(),
            "height": media.get_height(),
            "orientation": self._orientation.value,
        }

    def get_printable(self, page_index: int) -> PDFPrintable:
        printable = PDFPrintable(self._document, scaling=None)
        printable._page_index = page_index
        printable._subsampling_allowed = self._subsampling_allowed
        printable._rendering_hints = self._rendering_hints
        return printable


__all__ = ["PDFPageable", "Orientation"]

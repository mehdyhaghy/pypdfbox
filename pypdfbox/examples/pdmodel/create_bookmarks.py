"""Port of ``org.apache.pdfbox.examples.pdmodel.CreateBookmarks`` (lines 37-103).

Adds one bookmark for every page of a PDF.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    pd_page_fit_width_destination as _fitwidth,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    pd_document_outline as _outline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    pd_outline_item as _outline_item,
)
from pypdfbox.pdmodel.page_mode import PageMode
from pypdfbox.pdmodel.pd_document import PDDocument

PDPageFitWidthDestination = _fitwidth.PDPageFitWidthDestination
PDDocumentOutline = _outline.PDDocumentOutline
PDOutlineItem = _outline_item.PDOutlineItem


class CreateBookmarks:
    """Mirrors ``CreateBookmarks`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 51)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            CreateBookmarks.usage()
            return
        with PDDocument.load(argv[0]) as document:
            if document.is_encrypted():
                sys.stderr.write(
                    "Error: Cannot add bookmarks to encrypted document.\n",
                )
                raise SystemExit(1)
            outline = PDDocumentOutline()
            document.get_document_catalog().set_document_outline(outline)
            pages_outline = PDOutlineItem()
            pages_outline.set_title("All Pages")
            outline.add_last(pages_outline)
            for page_num, page in enumerate(document.get_pages(), start=1):
                dest = PDPageFitWidthDestination()
                dest.set_page(page)
                bookmark = PDOutlineItem()
                bookmark.set_destination(dest)
                bookmark.set_title(f"Page {page_num}")
                pages_outline.add_last(bookmark)
            pages_outline.open_node()
            outline.open_node()
            document.get_document_catalog().set_page_mode(PageMode.USE_OUTLINES)
            document.save(argv[1])

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "Usage: CreateBookmarks <input-pdf> <output-pdf>\n",
        )

"""Port of ``org.apache.pdfbox.examples.pdmodel.GoToSecondBookmarkOnOpen`` (lines 34-92).

Sets the open-action of a document so that opening it jumps to the second
top-level bookmark.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.pd_document import PDDocument


class GoToSecondBookmarkOnOpen:
    """Mirrors ``GoToSecondBookmarkOnOpen`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 48)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            GoToSecondBookmarkOnOpen.usage()
            return
        with PDDocument.load(argv[0]) as document:
            if document.is_encrypted():
                sys.stderr.write(
                    "Error: Cannot add bookmark destination to encrypted "
                    "documents.\n",
                )
                raise SystemExit(1)
            if document.get_number_of_pages() < 2:
                raise OSError(
                    "Error: The PDF must have at least 2 pages.",
                )
            bookmarks = document.get_document_catalog().get_document_outline()
            if bookmarks is None:
                raise OSError(
                    "Error: The PDF does not contain any bookmarks",
                )
            item = bookmarks.get_first_child().get_next_sibling()
            dest = item.get_destination()
            action = PDActionGoTo()
            action.set_destination(dest)
            document.get_document_catalog().set_open_action(action)
            document.save(argv[1])

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "Usage: GoToSecondBookmarkOnOpen <input-pdf> <output-pdf>\n",
        )

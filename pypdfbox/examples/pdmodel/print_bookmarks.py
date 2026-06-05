"""Port of ``org.apache.pdfbox.examples.pdmodel.PrintBookmarks`` (lines 37-145).

Prints a document's outline (bookmarks) to stdout.
"""

from __future__ import annotations

import sys
from typing import Any

from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument


class PrintBookmarks:
    """Mirrors ``PrintBookmarks`` (line 37)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 46)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            PrintBookmarks.usage()
            return
        with PDDocument.load(argv[0]) as document:
            meta = PrintBookmarks()
            outline = document.get_document_catalog().get_document_outline()
            if outline is not None:
                meta.print_bookmark(document, outline, "")
            else:
                sys.stdout.write("This document does not contain any bookmarks\n")

    @staticmethod
    def usage() -> None:
        sys.stderr.write("Usage: PrintBookmarks <input-pdf>\n")

    def print_bookmark(
        self,
        document: PDDocument,
        bookmark: Any,
        indentation: str,
    ) -> None:
        """Mirrors ``printBookmark`` (line 87)."""
        current = bookmark.get_first_child()
        while current is not None:
            dest = current.get_destination()
            if isinstance(dest, PDPageDestination):
                sys.stdout.write(
                    f"{indentation}Destination page: "
                    f"{dest.retrieve_page_number() + 1}\n",
                )
            elif isinstance(dest, PDNamedDestination):
                pd = document.get_document_catalog().find_named_destination_page(dest)
                if pd is not None:
                    sys.stdout.write(
                        f"{indentation}Destination page: "
                        f"{pd.retrieve_page_number() + 1}\n",
                    )
            elif dest is not None:
                sys.stdout.write(
                    f"{indentation}Destination class: {type(dest).__name__}\n",
                )

            action = current.get_action()
            if isinstance(action, PDActionGoTo):
                action_dest = action.get_destination()
                if isinstance(action_dest, PDPageDestination):
                    sys.stdout.write(
                        f"{indentation}Destination page: "
                        f"{action_dest.retrieve_page_number() + 1}\n",
                    )
                elif isinstance(action_dest, PDNamedDestination):
                    # ``PDActionGoTo.get_destination`` returns a
                    # ``PDNamedDestination`` for the name/string form
                    # (upstream parity, wave 1491), so this arm mirrors
                    # upstream ``PrintBookmarks`` exactly.
                    pd = document.get_document_catalog().find_named_destination_page(action_dest)
                    if pd is not None:
                        sys.stdout.write(
                            f"{indentation}Destination page: "
                            f"{pd.retrieve_page_number() + 1}\n",
                        )
                else:
                    sys.stdout.write(
                        f"{indentation}Destination class: "
                        f"{type(action_dest).__name__}\n",
                    )
            elif action is not None:
                sys.stdout.write(
                    f"{indentation}Action class: {type(action).__name__}\n",
                )

            sys.stdout.write(f"{indentation}{current.get_title()}\n")
            self.print_bookmark(document, current, indentation + "    ")
            current = current.get_next_sibling()

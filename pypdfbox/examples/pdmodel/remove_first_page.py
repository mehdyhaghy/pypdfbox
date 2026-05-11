"""Port of ``org.apache.pdfbox.examples.pdmodel.RemoveFirstPage`` (lines 33-79).

Removes the first page of a PDF document.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.pd_document import PDDocument


class RemoveFirstPage:
    """Mirrors ``RemoveFirstPage`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 47)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            RemoveFirstPage.usage()
            return
        with PDDocument.load(argv[0]) as document:
            if document.is_encrypted():
                raise OSError(
                    "Encrypted documents are not supported for this example",
                )
            if document.get_number_of_pages() <= 1:
                raise OSError(
                    "Error: A PDF document must have at least one page, "
                    "cannot remove the last page!",
                )
            document.remove_page(0)
            document.save(argv[1])

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "Usage: RemoveFirstPage <input-pdf> <output-pdf>\n",
        )



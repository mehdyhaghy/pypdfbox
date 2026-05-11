"""Port of ``org.apache.pdfbox.examples.pdmodel.CreateBlankPDF`` (lines 27-51).

Create a blank PDF and write the contents to a file.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


class CreateBlankPDF:
    """Mirrors ``CreateBlankPDF`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 33)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            sys.stderr.write("usage: CreateBlankPDF <outputfile.pdf>\n")
            raise SystemExit(1)
        filename = argv[0]
        with PDDocument() as doc:
            # A valid PDF document requires at least one page.
            blank_page = PDPage()
            doc.add_page(blank_page)
            doc.save(filename)

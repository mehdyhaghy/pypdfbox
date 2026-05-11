"""Port of ``ExtractTextByArea`` (upstream ``ExtractTextByArea.java``
lines 33-78).

Demonstrates region-based text extraction with :class:`PDFTextStripperByArea`.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text.pdf_text_stripper_by_area import PDFTextStripperByArea


class ExtractTextByArea:
    """Mirrors ``ExtractTextByArea`` (final, package-private ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    ExtractTextByArea.java`` (lines 33-78).
    """

    def __init__(self) -> None:
        # Upstream marks the class final / utility-only.
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> str:
        """Entry point — mirrors ``main(String[] args)`` (line 48).

        Returns the extracted region text so test callers can inspect it;
        upstream writes it to ``System.out``."""
        argv = list(argv) if argv else []
        if len(argv) != 1:
            ExtractTextByArea.usage()
            return ""
        return ExtractTextByArea.extract_region(argv[0])

    @staticmethod
    def extract_region(
        filename: str,
        x: float = 10,
        y: float = 280,
        w: float = 275,
        h: float = 60,
    ) -> str:
        """Extract text from a single region of the first page. Promoted
        from the upstream inline ``main`` body."""
        with PDDocument.load(filename) as document:
            stripper = PDFTextStripperByArea()
            stripper.set_sort_by_position(True)
            rect = PDRectangle(x, y, w, h)
            try:
                stripper.add_region("class1", rect)
            except TypeError:
                # Some pypdfbox builds typed the region as a stdlib
                # Rectangle — fall back to a tuple.
                stripper.add_region("class1", (x, y, w, h))  # type: ignore[arg-type]
            first_page = document.get_page(0)
            stripper.extract_regions(first_page)
            text = stripper.get_text_for_region("class1")
            sys.stdout.write(f"Text in the area:{rect}\n{text}\n")
            return text

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 73)."""
        sys.stderr.write("Usage: ExtractTextByArea <input-pdf>\n")


if __name__ == "__main__":  # pragma: no cover
    ExtractTextByArea.main(sys.argv[1:])

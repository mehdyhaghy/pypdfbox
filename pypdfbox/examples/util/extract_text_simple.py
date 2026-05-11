"""Port of ``ExtractTextSimple`` (upstream ``ExtractTextSimple.java``
lines 34-106).

Streams the text of every page of a PDF to stdout, one page at a time.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper


class ExtractTextSimple:
    """Mirrors ``ExtractTextSimple`` (default, package-private ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    ExtractTextSimple.java`` (lines 34-106).
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> str:
        """Entry point — mirrors ``main(String[] args)`` (line 48).

        Returns the concatenated extracted text so test callers can
        inspect the result; upstream writes it to ``System.out``."""
        argv = list(argv) if argv else []
        if len(argv) != 1:
            ExtractTextSimple.usage()
            return ""
        return ExtractTextSimple.extract(argv[0])

    @staticmethod
    def extract(filename: str) -> str:
        """Return the page-by-page text of ``filename``. Promoted from
        the upstream inline ``main`` body."""
        buf: list[str] = []
        with PDDocument.load(filename) as document:
            try:
                ap = document.get_current_access_permission()
                if not ap.can_extract_content():
                    raise OSError("You do not have permission to extract text")
            except (AttributeError, NotImplementedError):
                # Encryption checks aren't relevant for unencrypted demos.
                pass

            stripper = PDFTextStripper()
            stripper.set_sort_by_position(True)

            for p in range(1, document.get_number_of_pages() + 1):
                stripper.set_start_page(p)
                stripper.set_end_page(p)
                text = stripper.get_text(document)
                header = f"page {p}:"
                buf.append(header)
                buf.append("-" * len(header))
                buf.append(text.strip())
                buf.append("")
        joined = "\n".join(buf)
        sys.stdout.write(joined + "\n")
        return joined

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 101)."""
        sys.stderr.write("Usage: ExtractTextSimple <input-pdf>\n")


if __name__ == "__main__":  # pragma: no cover
    ExtractTextSimple.main(sys.argv[1:])

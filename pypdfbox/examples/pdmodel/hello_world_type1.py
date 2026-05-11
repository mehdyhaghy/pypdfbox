"""Port of ``org.apache.pdfbox.examples.pdmodel.HelloWorldType1`` (lines 32-76).

Creates a simple document with a Type 1 font (.pfb).
"""

from __future__ import annotations

import sys
from pathlib import Path

from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


class HelloWorldType1:
    """Mirrors ``HelloWorldType1`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 39)."""
        argv = argv if argv is not None else []
        if len(argv) != 3:
            sys.stderr.write(
                "usage: HelloWorldType1 <output-file> <Message> <pfb-file>\n",
            )
            raise SystemExit(1)
        file_, message, pfb_path = argv[0], argv[1], argv[2]
        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)
            with Path(pfb_path).open("rb") as is_:
                font = PDType1Font(doc, is_)
            with PDPageContentStream(doc, page) as contents:
                contents.begin_text()
                contents.set_font(font, 12)
                contents.new_line_at_offset(100, 700)
                contents.show_text(message)
                contents.end_text()
            doc.save(file_)
            sys.stdout.write(f"{file_} created!\n")

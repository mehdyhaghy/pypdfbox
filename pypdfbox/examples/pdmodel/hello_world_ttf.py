"""Port of ``org.apache.pdfbox.examples.pdmodel.HelloWorldTTF`` (lines 31-70).

Creates a simple document with a TrueType font.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


class HelloWorldTTF:
    """Mirrors ``HelloWorldTTF`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 37)."""
        argv = argv if argv is not None else []
        if len(argv) != 3:
            sys.stderr.write(
                "usage: HelloWorldTTF <output-file> <Message> <ttf-file>\n",
            )
            raise SystemExit(1)
        pdf_path, message, ttf_path = argv[0], argv[1], argv[2]
        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)
            font = PDType0Font.load(doc, ttf_path)
            with PDPageContentStream(doc, page) as contents:
                contents.begin_text()
                contents.set_font(font, 12)
                contents.new_line_at_offset(100, 700)
                contents.show_text(message)
                contents.end_text()
            doc.save(pdf_path)
            sys.stdout.write(f"{pdf_path} created!\n")

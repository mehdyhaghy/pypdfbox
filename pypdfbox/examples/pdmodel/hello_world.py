"""Port of ``org.apache.pdfbox.examples.pdmodel.HelloWorld`` (lines 35-71).

Creates a "Hello World" PDF using the built-in Helvetica font.
"""

from __future__ import annotations

import sys

from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


class HelloWorld:
    """Mirrors ``HelloWorld`` (final, package-private constructor)."""

    def __init__(self) -> None:
        # Upstream marks the class final with a private no-arg constructor.
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 41)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            sys.stderr.write(
                "usage: HelloWorld <output-file> <Message>\n",
            )
            raise SystemExit(1)
        filename = argv[0]
        message = argv[1]

        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)
            font = make_standard14_type1_font(FontName.HELVETICA_BOLD)
            with PDPageContentStream(doc, page) as contents:
                contents.begin_text()
                contents.set_font(font, 12)
                contents.new_line_at_offset(100, 700)
                contents.show_text(message)
                contents.end_text()
            doc.save(filename)

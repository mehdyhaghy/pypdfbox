"""Port of ``org.apache.pdfbox.examples.pdmodel.CreateLandscapePDF`` (lines 34-128).

Creates a sample document with a landscape orientation and some text
surrounded by a box.
"""

from __future__ import annotations

import sys

from pypdfbox.examples.pdmodel._font_helpers import (
    apply_transform,
    make_standard14_type1_font,
)
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.util.matrix import Matrix


class CreateLandscapePDF:
    """Mirrors ``CreateLandscapePDF`` (line 34)."""

    def __init__(self) -> None:
        # Upstream public no-arg constructor.
        pass

    def do_it(self, message: str, outfile: str) -> None:
        """Mirrors ``doIt(String message, String outfile)`` (line 52)."""
        with PDDocument() as doc:
            font = make_standard14_type1_font(FontName.HELVETICA)
            page = PDPage(PDRectangle.A4)
            page.set_rotation(90)
            doc.add_page(page)
            page_size = page.get_media_box()
            page_width = page_size.get_width()
            font_size = 12.0
            string_width = font.get_string_width(message) * font_size / 1000.0
            start_x = 100.0
            start_y = 100.0
            with PDPageContentStream(
                doc, page, AppendMode.OVERWRITE, False,
            ) as cs:
                # Add the rotation using the current transformation matrix
                # including a translation of pageWidth so the lower-left
                # corner is the (0, 0) reference.
                apply_transform(cs, Matrix(0, 1, -1, 0, page_width, 0))
                cs.set_font(font, font_size)
                cs.begin_text()
                cs.new_line_at_offset(start_x, start_y)
                cs.show_text(message)
                cs.new_line_at_offset(0, 100)
                cs.show_text(message)
                cs.new_line_at_offset(100, 100)
                cs.show_text(message)
                cs.end_text()

                cs.move_to(start_x - 2, start_y - 2)
                cs.line_to(start_x - 2, start_y + 200 + font_size)
                cs.stroke()
                cs.move_to(start_x - 2, start_y + 200 + font_size)
                cs.line_to(
                    start_x + 100 + string_width + 2,
                    start_y + 200 + font_size,
                )
                cs.stroke()
                cs.move_to(
                    start_x + 100 + string_width + 2,
                    start_y + 200 + font_size,
                )
                cs.line_to(start_x + 100 + string_width + 2, start_y - 2)
                cs.stroke()
                cs.move_to(start_x + 100 + string_width + 2, start_y - 2)
                cs.line_to(start_x - 2, start_y - 2)
                cs.stroke()
            doc.save(outfile)

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 108)."""
        argv = argv if argv is not None else []
        app = CreateLandscapePDF()
        if len(argv) != 2:
            CreateLandscapePDF.usage()
        else:
            app.do_it(argv[0], argv[1])

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "usage: CreateLandscapePDF <Message> <output-file>\n",
        )

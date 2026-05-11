"""Port of ``org.apache.pdfbox.examples.pdmodel.UsingTextMatrix`` (lines 34-162).

Demonstrates a variety of text-matrix transforms across three pages.
"""

from __future__ import annotations

import math
import sys

from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.util.matrix import Matrix


class UsingTextMatrix:
    """Mirrors ``UsingTextMatrix`` (line 34)."""

    def __init__(self) -> None:
        # Upstream public no-arg constructor.
        pass

    def do_it(self, message: str, outfile: str) -> None:
        """Mirrors ``doIt(String message, String outfile)`` (line 51)."""
        with PDDocument() as doc:
            # Page 1 — rotation grid.
            font = make_standard14_type1_font(FontName.HELVETICA)
            page = PDPage(PDRectangle.A4)
            doc.add_page(page)
            font_size = 12.0
            page_size = page.get_media_box()
            centered_x = (page_size.get_width() - font_size / 1000.0) / 2.0
            string_width = font.get_string_width(message)
            centered_y = (
                page_size.get_height() - (string_width * font_size) / 1000.0
            ) / 3.0
            cs = PDPageContentStream(doc, page, AppendMode.OVERWRITE, False)
            cs.set_font(font, font_size)
            cs.begin_text()
            for i in range(8):
                cs.set_text_matrix(
                    Matrix.get_rotate_instance(
                        i * math.pi * 0.25,
                        centered_x,
                        page_size.get_height() - centered_y,
                    ),
                )
                cs.show_text(f"{message} {i}")
            for i in range(8):
                cs.set_text_matrix(
                    Matrix.get_rotate_instance(
                        -i * math.pi * 0.25,
                        centered_x,
                        centered_y,
                    ),
                )
                cs.show_text(f"{message} {i}")
            cs.end_text()
            cs.close()

            # Page 2 — scaling.
            page = PDPage(PDRectangle.A4)
            doc.add_page(page)
            font_size = 1.0
            cs = PDPageContentStream(doc, page, AppendMode.OVERWRITE, False)
            cs.set_font(font, font_size)
            cs.begin_text()
            for i in range(10):
                cs.set_text_matrix(
                    Matrix(
                        12.0 + (i * 6),
                        0,
                        0,
                        12.0 + (i * 6),
                        100,
                        100.0 + i * 50,
                    ),
                )
                cs.show_text(f"{message} {i}")
            cs.end_text()
            cs.close()

            # Page 3 — scaling combined with rotation.
            page = PDPage(PDRectangle.A4)
            doc.add_page(page)
            font_size = 1.0
            cs = PDPageContentStream(doc, page, AppendMode.OVERWRITE, False)
            cs.set_font(font, font_size)
            cs.begin_text()
            i = 0
            cs.set_text_matrix(
                Matrix(12, 0, 0, 12, centered_x, centered_y * 1.5),
            )
            cs.show_text(f"{message} {i}")
            i += 1
            cs.set_text_matrix(
                Matrix(0, 18, -18, 0, centered_x, centered_y * 1.5),
            )
            cs.show_text(f"{message} {i}")
            i += 1
            cs.set_text_matrix(
                Matrix(-24, 0, 0, -24, centered_x, centered_y * 1.5),
            )
            cs.show_text(f"{message} {i}")
            i += 1
            cs.set_text_matrix(
                Matrix(0, -30, 30, 0, centered_x, centered_y * 1.5),
            )
            cs.show_text(f"{message} {i}")
            cs.end_text()
            cs.close()

            doc.save(outfile)

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 142)."""
        argv = argv if argv is not None else []
        app = UsingTextMatrix()
        if len(argv) != 2:
            app.usage()
        else:
            app.do_it(argv[0], argv[1])

    def usage(self) -> None:
        sys.stderr.write(
            "usage: UsingTextMatrix <Message> <output-file>\n",
        )

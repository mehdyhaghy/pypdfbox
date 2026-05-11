"""Port of ``org.apache.pdfbox.examples.pdmodel.AddMessageToEachPage`` (lines 40-131).

Adds a centered message to every page of a PDF document.
"""

from __future__ import annotations

import math
import sys

from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from pypdfbox.util.matrix import Matrix


class AddMessageToEachPage:
    """Mirrors ``AddMessageToEachPage`` (line 40)."""

    def __init__(self) -> None:
        pass

    def do_it(self, file_: str, message: str, outfile: str) -> None:
        """Mirrors ``doIt(String file, String message, String outfile)`` (line 59)."""
        with PDDocument.load(file_) as doc:
            font = make_standard14_type1_font(FontName.HELVETICA_BOLD)
            font_size = 36.0
            for page in doc.get_pages():
                page_size = page.get_media_box()
                string_width = font.get_string_width(message) * font_size / 1000.0
                rotation = page.get_rotation()
                rotate = rotation in (90, 270)
                page_width = (
                    page_size.get_height() if rotate else page_size.get_width()
                )
                page_height = (
                    page_size.get_width() if rotate else page_size.get_height()
                )
                if rotate:
                    center_x = page_height / 2.0
                    center_y = (page_width - string_width) / 2.0
                else:
                    center_x = (page_width - string_width) / 2.0
                    center_y = page_height / 2.0
                with PDPageContentStream(
                    doc, page, AppendMode.APPEND, True, True,
                ) as cs:
                    cs.begin_text()
                    cs.set_font(font, font_size)
                    # set text color to red
                    cs.set_non_stroking_color_rgb(1, 0, 0)
                    if rotate:
                        cs.set_text_matrix(
                            Matrix.get_rotate_instance(
                                math.pi / 2, center_x, center_y,
                            ),
                        )
                    else:
                        cs.set_text_matrix(
                            Matrix.get_translate_instance(center_x, center_y),
                        )
                    cs.show_text(message)
                    cs.end_text()
            doc.save(outfile)

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 111)."""
        argv = argv if argv is not None else []
        app = AddMessageToEachPage()
        if len(argv) != 3:
            app.usage()
        else:
            app.do_it(argv[0], argv[1], argv[2])

    def usage(self) -> None:
        sys.stderr.write(
            "usage: AddMessageToEachPage <input-file> <Message> <output-file>\n",
        )

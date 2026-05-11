"""Port of ``org.apache.pdfbox.examples.pdmodel.SuperimposePage`` (lines 36-98).

Superimposes a page from a source PDF onto a fresh page in a new PDF using
``LayerUtility``.
"""

from __future__ import annotations

import math
import sys


class SuperimposePage:
    """Mirrors ``SuperimposePage`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 43)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            sys.stderr.write(
                "usage: SuperimposePage <source-pdf> <dest-pdf>\n",
            )
            raise SystemExit(1)
        source_path = argv[0]
        dest_path = argv[1]

        from pypdfbox.examples.pdmodel._font_helpers import (
            make_standard14_type1_font,
        )
        from pypdfbox.loader import Loader
        from pypdfbox.multipdf.layer_utility import LayerUtility
        from pypdfbox.pdmodel.font.standard14_fonts import FontName
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.pdmodel.pd_page import PDPage
        from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle
        from pypdfbox.util.matrix import Matrix

        with Loader.load_pdf(source_path) as source_cos_doc:
            source_doc = PDDocument(source_cos_doc)
            source_page = 1
            with PDDocument() as doc:
                page = PDPage()
                doc.add_page(page)
                with PDPageContentStream(doc, page) as contents:
                    contents.begin_text()
                    contents.set_font(
                        make_standard14_type1_font(FontName.HELVETICA_BOLD), 12,
                    )
                    contents.new_line_at_offset(2, PDRectangle.LETTER.get_height() - 12)
                    contents.show_text("Sample text")
                    contents.end_text()

                    # Create a Form XObject from the source document using LayerUtility.
                    layer_utility = LayerUtility(doc)
                    form = layer_utility.import_page_as_form(
                        source_doc, source_page - 1,
                    )

                    # Draw the full form.
                    contents.draw_form(form)

                    def _emit_cm(m: Matrix) -> None:
                        # Pull a, b, c, d, e, f from the flat 3x3 layout.
                        a = m.get_value(0, 0)
                        b = m.get_value(0, 1)
                        c = m.get_value(1, 0)
                        d = m.get_value(1, 1)
                        e = m.get_value(2, 0)
                        f = m.get_value(2, 1)
                        contents.transform(a, b, c, d, e, f)

                    # Draw a scaled form.
                    contents.save_graphics_state()
                    matrix = Matrix.get_scale_instance(0.5, 0.5)
                    _emit_cm(matrix)
                    contents.draw_form(form)
                    contents.restore_graphics_state()

                    # Draw a scaled and rotated form.
                    contents.save_graphics_state()
                    matrix.rotate(1.8 * math.pi)  # radians
                    _emit_cm(matrix)
                    contents.draw_form(form)
                    contents.restore_graphics_state()
                doc.save(dest_path)

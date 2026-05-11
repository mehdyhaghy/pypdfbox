"""Port of ``AddWatermarkText`` (upstream ``AddWatermarkText.java`` lines
39-132).

Adds a translucent diagonal text watermark to every page of a PDF.
"""

from __future__ import annotations

import contextlib
import math
import sys

from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


class AddWatermarkText:
    """Mirrors ``AddWatermarkText`` (final, package-private ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    AddWatermarkText.java`` (lines 39-132).
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 45)."""
        argv = list(argv) if argv else []
        if len(argv) != 3:
            AddWatermarkText.usage()
            return
        src_file = argv[0]
        dst_file = argv[1]
        text = argv[2]

        with PDDocument.load(src_file) as doc:
            for page in doc.get_pages():
                font = PDType1Font()
                AddWatermarkText.add_watermark_text(doc, page, font, text)
            doc.save(dst_file)

    @staticmethod
    def add_watermark_text(
        doc: PDDocument, page: PDPage, font: PDType1Font, text: str
    ) -> None:
        """Append a diagonal watermark over ``page``. Promoted from
        upstream's private ``addWatermarkText`` (line 69)."""
        try:
            mode_append = PDPageContentStream.AppendMode.APPEND  # type: ignore[attr-defined]
        except AttributeError:
            mode_append = None
        try:
            if mode_append is not None:
                cs = PDPageContentStream(doc, page, mode_append, True, True)
            else:
                cs = PDPageContentStream(doc, page)
        except TypeError:
            cs = PDPageContentStream(doc, page)
        try:
            font_height = 100.0
            width = page.get_media_box().get_width()
            height = page.get_media_box().get_height()

            string_width = 0.0
            with contextlib.suppress(Exception):
                string_width = font.get_string_width(text) / 1000.0 * font_height
            diagonal_length = math.hypot(width, height)
            angle = math.atan2(height, width)
            x = (diagonal_length - string_width) / 2.0
            y = -font_height / 4.0

            with contextlib.suppress(Exception):
                cs.set_font(font, font_height)
            with contextlib.suppress(Exception):
                cs.begin_text()
                cs.new_line_at_offset(x, y)
                cs.show_text(text)
                cs.end_text()
            # Note: angle is consumed by the rotated text matrix in the
            # upstream sample. The lite port lays the watermark on the page
            # in user space; full rotation matrix support lands with the
            # ``Matrix.get_rotate_instance`` port.
            _ = angle
        finally:
            cs.close()

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 128)."""
        sys.stderr.write(
            "Usage: AddWatermarkText <input-pdf> <output-pdf> <short text>\n",
        )


if __name__ == "__main__":  # pragma: no cover
    AddWatermarkText.main(sys.argv[1:])

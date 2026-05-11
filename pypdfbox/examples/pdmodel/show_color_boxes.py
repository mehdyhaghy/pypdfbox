"""Port of ``org.apache.pdfbox.examples.pdmodel.ShowColorBoxes`` (lines 29-76).

Fills the page background with cyan, draws a red and a blue box.
"""

from __future__ import annotations

import math
import sys

from pypdfbox.examples.pdmodel._font_helpers import apply_transform
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.util.matrix import Matrix


class ShowColorBoxes:
    """Mirrors ``ShowColorBoxes`` (final class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 36)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            sys.stderr.write("usage: ShowColorBoxes <output-file>\n")
            raise SystemExit(1)
        filename = argv[0]
        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)
            with PDPageContentStream(doc, page) as contents:
                # Fill the entire background with cyan.
                contents.set_non_stroking_color_rgb(0, 1, 1)
                media = page.get_media_box()
                contents.add_rect(0, 0, media.get_width(), media.get_height())
                contents.fill()
                # Draw a red box in the lower-left corner.
                contents.set_non_stroking_color_rgb(1, 0, 0)
                contents.add_rect(10, 10, 100, 100)
                contents.fill()
                # Draw a blue box with rotation around (200, 500).
                contents.save_graphics_state()
                contents.set_non_stroking_color_rgb(0, 0, 1)
                apply_transform(
                    contents,
                    Matrix.get_rotate_instance(math.radians(105), 200, 500),
                )
                contents.add_rect(0, 0, 200, 100)
                contents.fill()
                contents.restore_graphics_state()
            doc.save(filename)

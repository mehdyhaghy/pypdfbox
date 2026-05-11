"""Port of ``org.apache.pdfbox.examples.pdmodel.AddImageToPDF`` (lines 36-99).

Adds an image to an existing PDF document.
"""

from __future__ import annotations

import sys


class AddImageToPDF:
    """Mirrors ``AddImageToPDF``."""

    def __init__(self) -> None:
        pass

    def create_pdf_from_image(
        self,
        input_file: str,
        image_path: str,
        output_file: str,
    ) -> None:
        """Mirrors ``createPDFFromImage`` (line 47).

        Loads ``input_file``, drops the image at ``image_path`` onto the first
        page at (20, 20) using the image's intrinsic pixel dimensions
        (``scale = 1``), then writes to ``output_file``. The Append-mode
        content stream preserves any existing page content (upstream
        L60: ``AppendMode.APPEND, true, true``).
        """
        from pypdfbox.loader import Loader
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
            PDImageXObject,
        )
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.pdmodel.pd_page_content_stream import (
            AppendMode,
            PDPageContentStream,
        )

        # ``pypdfbox.Loader.load_pdf`` returns a ``COSDocument`` (lower-level
        # than upstream's ``PDDocument``); wrap it explicitly so the
        # high-level page / save API mirrors the Java example.
        with Loader.load_pdf(input_file) as cos_doc:
            doc = PDDocument(cos_doc)
            page = doc.get_page(0)
            pd_image = PDImageXObject.create_from_file(image_path, doc)
            with PDPageContentStream(
                doc, page, AppendMode.APPEND, True, True,
            ) as content_stream:
                scale = 1.0
                content_stream.draw_image(
                    pd_image,
                    20,
                    20,
                    pd_image.get_width() * scale,
                    pd_image.get_height() * scale,
                )
            doc.save(output_file)

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 79)."""
        argv = argv if argv is not None else []
        app = AddImageToPDF()
        if len(argv) != 3:
            app.usage()
        else:
            app.create_pdf_from_image(argv[0], argv[1], argv[2])

    def usage(self) -> None:
        sys.stderr.write(
            "usage: AddImageToPDF <input-pdf> <image> <output-pdf>\n",
        )

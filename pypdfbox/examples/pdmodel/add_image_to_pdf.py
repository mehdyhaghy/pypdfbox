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
        """Mirrors ``createPDFFromImage`` (line 47)."""
        # TODO: PDImageXObject.create_from_file is part of the graphics.image
        # subsystem; the wave-1283 port does not yet bind it here.
        raise NotImplementedError(
            "AddImageToPDF requires PDImageXObject.create_from_file; port "
            "pending exposure of the graphics.image API surface.",
        )

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

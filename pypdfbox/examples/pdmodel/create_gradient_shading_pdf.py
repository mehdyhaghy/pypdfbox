"""Port of ``org.apache.pdfbox.examples.pdmodel.CreateGradientShadingPDF`` (lines 46-220).

Creates a PDF with axial, radial, and Gouraud shadings.
"""

from __future__ import annotations

import sys


class CreateGradientShadingPDF:
    """Mirrors ``CreateGradientShadingPDF`` (line 46)."""

    def __init__(self) -> None:
        pass

    def create(self, file_: str) -> None:
        """Mirrors ``create(String file)`` (line 56)."""
        del file_
        # TODO: gradient shadings require PDFunctionType2, PDShadingType2/3/4
        # plus raw vertex stream emission. A faithful port lands in a later
        # wave.
        raise NotImplementedError(
            "CreateGradientShadingPDF awaits PDShading* exposure in the "
            "examples surface.",
        )

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 200)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            CreateGradientShadingPDF.usage()
            return
        creator = CreateGradientShadingPDF()
        creator.create(argv[0])

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream line 215)."""
        sys.stderr.write(
            "usage: CreateGradientShadingPDF <outputfile.pdf>\n",
        )

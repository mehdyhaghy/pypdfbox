"""Port of ``org.apache.pdfbox.examples.pdmodel.AddAnnotations`` (lines 53-356).

Adds a variety of annotations to a 3-page PDF document.
"""

from __future__ import annotations

import sys

#: Mirrors upstream's ``INCH = 72`` package-private constant (line 55).
INCH: float = 72.0


class AddAnnotations:
    """Mirrors ``AddAnnotations`` (final, utility class)."""

    INCH: float = INCH

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 61)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            sys.stderr.write("Usage: AddAnnotations <output-pdf>\n")
            raise SystemExit(1)
        # TODO: AddAnnotations exercises a very large slice of the annotation
        # subsystem (PDAnnotationHighlight, PDAnnotationFreeText,
        # PDAnnotationPolygon, PDAnnotationLine, PDBorderStyleDictionary,
        # PDPageFitWidthDestination, PDActionURI / PDActionGoTo wiring,
        # constructAppearances, AcroForm default resources, PDType0Font.load
        # from a resource stream). A faithful port lands in a later wave.
        raise NotImplementedError(
            "AddAnnotations awaits a full pass over the annotation subsystem "
            "and AcroForm default-resources wiring.",
        )

    @staticmethod
    def show_page_no(document: object, page: object, page_text: str) -> None:
        """Mirrors ``showPageNo(PDDocument, PDPage, String)`` (line 337)."""
        del document, page, page_text  # see ``main``.
        raise NotImplementedError(
            "show_page_no requires the full content-stream surface; see main.",
        )

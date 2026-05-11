"""Port of ``org.apache.pdfbox.examples.pdmodel.RubberStamp`` (lines 35-87).

Adds a rubber-stamp annotation to every page of a PDF.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class RubberStamp:
    """Mirrors ``RubberStamp`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 49)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            RubberStamp.usage()
            return
        with PDDocument.load(argv[0]) as document:
            if document.is_encrypted():
                raise OSError(
                    "Encrypted documents are not supported for this example",
                )
            for page in document.get_pages():
                annotations = page.get_annotations()
                rs = PDAnnotationRubberStamp()
                rs.set_name(PDAnnotationRubberStamp.NAME_TOP_SECRET)
                rs.set_rectangle(PDRectangle(100, 100))
                rs.set_contents("A top secret note")
                annotations.append(rs)
            document.save(argv[1])

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "Usage: RubberStamp <input-pdf> <output-pdf>\n",
        )

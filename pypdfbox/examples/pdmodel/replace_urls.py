"""Port of ``org.apache.pdfbox.examples.pdmodel.ReplaceURLs`` (lines 39-114).

Replaces every URL link in a PDF with ``http://pdfbox.apache.org``.
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.pd_document import PDDocument


class ReplaceURLs:
    """Mirrors ``ReplaceURLs`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 59)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            ReplaceURLs.usage()
            return
        with PDDocument.load(argv[0]) as doc:
            for page_num, page in enumerate(doc.get_pages(), start=1):
                annotations = page.get_annotations()
                for annot in annotations:
                    if isinstance(annot, PDAnnotationLink):
                        action = annot.get_action()
                        if isinstance(action, PDActionURI):
                            old_uri = action.get_uri()
                            new_uri = "http://pdfbox.apache.org"
                            sys.stdout.write(
                                f"Page {page_num}: Replacing {old_uri} with "
                                f"{new_uri}\n",
                            )
                            action.set_uri(new_uri)
            doc.save(argv[1])

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "usage: ReplaceURLs <input-file> <output-file>\n",
        )

"""Port of ``org.apache.pdfbox.examples.pdmodel.PrintURLs`` (lines 41-164).

Prints URLs in a PDF along with the text of the surrounding annotation
rectangle.
"""

from __future__ import annotations

import sys
from typing import Any


class PrintURLs:
    """Mirrors ``PrintURLs`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 60).

        Walks every page of the input PDF, gathers annotations that expose
        a ``PDActionURI``, defines a text-extraction region for each link
        rectangle (flipped from PDF to top-down coordinates when the page
        has zero rotation, matching upstream), then prints the text in the
        rectangle alongside the URI.
        """
        argv = argv if argv is not None else []
        if len(argv) != 1:
            PrintURLs.usage()
            return

        from pypdfbox.loader import Loader
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.text.pdf_text_stripper_by_area import PDFTextStripperByArea

        cos_doc = Loader.load_pdf(argv[0])
        try:
            doc = PDDocument(cos_doc)
            page_num = 0
            for page in doc.get_pages():
                page_num += 1
                stripper = PDFTextStripperByArea()
                annotations = page.get_annotations()
                # First setup text extraction regions.
                for j, annot in enumerate(annotations):
                    if PrintURLs.get_action_uri(annot) is None:
                        continue
                    rect = annot.get_rectangle()
                    if rect is None:
                        continue
                    x = rect.get_lower_left_x()
                    y = rect.get_upper_right_y()
                    width = rect.get_width()
                    height = rect.get_height()
                    rotation = page.get_rotation()
                    if rotation == 0:
                        page_size = page.get_media_box()
                        # Area stripper uses image coordinates, not PDF coordinates.
                        y = page_size.get_height() - y
                    # else: leave as-is — upstream comments "do nothing".
                    stripper.add_region(str(j), (x, y, width, height))
                stripper.extract_regions(page)
                for j, annot in enumerate(annotations):
                    uri = PrintURLs.get_action_uri(annot)
                    if uri is None:
                        continue
                    url_text = stripper.get_text_for_region(str(j))
                    print(f"Page {page_num}:'{url_text.strip()}'={uri.get_uri()}")
        finally:
            close = getattr(cos_doc, "close", None)
            if close is not None:
                close()

    @staticmethod
    def get_action_uri(annot: Any) -> Any:
        """Mirrors ``getActionURI(PDAnnotation)`` (line 133)."""
        # Use duck typing — any annotation that has a ``get_action`` method
        # returning a ``PDActionURI``.
        try:
            get_action = annot.get_action
        except AttributeError:
            return None
        try:
            action = get_action()
        except Exception:  # noqa: BLE001 — mirrors broad Java catch
            return None
        from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI

        if isinstance(action, PDActionURI):
            return action
        return None

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (line 158)."""
        sys.stderr.write("usage: PrintURLs <input-file>\n")

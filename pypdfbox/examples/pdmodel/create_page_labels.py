"""Port of ``org.apache.pdfbox.examples.pdmodel.CreatePageLabels`` (lines 30-60).

Create a 3-page PDF with page labels "RO III", "RO IV", "1".
"""

from __future__ import annotations

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange
from pypdfbox.pdmodel.pd_page_labels import PDPageLabels


class CreatePageLabels:
    """Mirrors ``CreatePageLabels`` (line 30)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 39)."""
        del argv  # upstream ignores args entirely
        with PDDocument() as doc:
            doc.add_page(PDPage())
            doc.add_page(PDPage())
            doc.add_page(PDPage())
            page_labels = PDPageLabels(doc)
            range1 = PDPageLabelRange()
            range1.set_prefix("RO ")
            range1.set_start(3)
            range1.set_style(PDPageLabelRange.STYLE_ROMAN_UPPER)
            page_labels.set_label_item(0, range1)
            range2 = PDPageLabelRange()
            range2.set_start(1)
            range2.set_style(PDPageLabelRange.STYLE_DECIMAL)
            page_labels.set_label_item(2, range2)
            doc.get_document_catalog().set_page_labels(page_labels)
            doc.save("labels.pdf")

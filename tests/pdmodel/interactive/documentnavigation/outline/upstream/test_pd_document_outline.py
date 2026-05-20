"""Port of upstream ``PDDocumentOutlineTest.java``.

Upstream path:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/documentnavigation/outline/PDDocumentOutlineTest.java``

Upstream baseline: PDFBox 3.0.x.
"""
from __future__ import annotations

from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)


def test_outlines_count_should_not_be_negative() -> None:
    """see PDF 32000-1:2008 table 152"""
    outline = PDDocumentOutline()
    first_level_child = PDOutlineItem()
    outline.add_last(first_level_child)
    second_level_child = PDOutlineItem()
    first_level_child.add_last(second_level_child)
    assert second_level_child.get_open_count() == 0
    assert first_level_child.get_open_count() == -1
    assert not outline.get_open_count() < 0, (
        f"Outlines count cannot be {outline.get_open_count()}"
    )


def test_outlines_count() -> None:
    outline = PDDocumentOutline()
    root = PDOutlineItem()
    outline.add_last(root)
    assert outline.get_open_count() == 1
    root.add_last(PDOutlineItem())
    assert root.get_open_count() == -1
    assert outline.get_open_count() == 1
    root.add_last(PDOutlineItem())
    assert root.get_open_count() == -2
    assert outline.get_open_count() == 1
    root.open_node()
    assert root.get_open_count() == 2
    assert outline.get_open_count() == 3

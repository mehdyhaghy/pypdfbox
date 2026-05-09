"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPage.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage  # noqa: F401 — referenced by skipped tests


# Skipped: ``testAddingPageAfterCreatingAnnotation`` — needs PDAcroForm /
# PDTextField / PDAnnotationWidget (pdmodel clusters #5 + #6).
@pytest.mark.skip(
    reason="needs PDAcroForm + PDAnnotationWidget — pdmodel clusters #5/#6"
)
def test_adding_page_after_creating_annotation() -> None:  # pragma: no cover
    pass


def test_null_thread_beads() -> None:
    page = PDPage()

    assert page.get_thread_beads() == []

    page.set_thread_beads([])
    assert page.get_thread_beads() == []

    page.set_thread_beads(None)
    assert page.get_thread_beads() == []

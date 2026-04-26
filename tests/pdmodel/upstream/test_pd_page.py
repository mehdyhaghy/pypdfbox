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


# Skipped: ``testNullThreadBeads`` — ``PDPage.get_thread_beads`` requires
# the article-thread machinery (pdmodel cluster #5 / interactive features).
@pytest.mark.skip(reason="PDPage.get_thread_beads — pdmodel cluster #5")
def test_null_thread_beads() -> None:  # pragma: no cover
    pass

"""Ported upstream tests for ``MergeAnnotations``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/multipdf/MergeAnnotationsTest.java``
(PDFBox 3.0.x).

Upstream's one test depends on PDFBOX-1065 corpus PDFs from
``target/pdfs/`` (Maven-downloaded). Skipped with a one-line reason.
The structural PDFMergerUtility / annotation-walking parity is covered
in ``test_pdf_merger_utility.py`` and the annotation-cluster tests
under ``tests/pdmodel/interactive/annotation/upstream/``.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="PDFBOX-1065: requires target/pdfs/PDFBOX-1065-{1,2}.pdf "
    "fixtures (Maven-downloaded corpus, two source docs whose link "
    "annotations reference each other via /Dests entries). Not "
    "bundled. The structural PDFMergerUtility surface + annotation "
    "walking are covered elsewhere."
)
def test_link_annotations() -> None: ...

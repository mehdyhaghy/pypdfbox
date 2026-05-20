"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPageAnnotationsFiltering.java

Upstream baseline: PDFBox 3.0.x. Validates the correct working behavior of
``PDPage`` annotations filtering. ``get_annotations(callable)`` mirrors
upstream's ``PDPage.getAnnotations(AnnotationFilter)`` — the filter callable
is invoked on every dispatched annotation; only annotations for which the
callable returns truthy are kept.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationLink,
    PDAnnotationRubberStamp,
    PDAnnotationSquare,
)


@pytest.fixture
def page() -> PDPage:
    mocked_page_with_annotations = COSDictionary()
    annots_dictionary = COSArray()
    annots_dictionary.add(PDAnnotationRubberStamp().get_cos_object())
    annots_dictionary.add(PDAnnotationSquare().get_cos_object())
    annots_dictionary.add(PDAnnotationLink().get_cos_object())
    mocked_page_with_annotations.set_item(COSName.get_pdf_name("Annots"), annots_dictionary)
    return PDPage(mocked_page_with_annotations)


def test_validate_no_filtering(page: PDPage) -> None:
    annotations = page.get_annotations()
    assert len(annotations) == 3
    assert isinstance(annotations[0], PDAnnotationRubberStamp)
    assert isinstance(annotations[1], PDAnnotationSquare)
    assert isinstance(annotations[2], PDAnnotationLink)


def test_validate_all_filtered(page: PDPage) -> None:
    annotations = page.get_annotations(lambda annotation: False)
    assert len(annotations) == 0


def test_validate_selected_few(page: PDPage) -> None:
    annotations = page.get_annotations(
        lambda annotation: isinstance(annotation, (PDAnnotationLink, PDAnnotationSquare))
    )
    assert len(annotations) == 2
    assert isinstance(annotations[0], PDAnnotationSquare)
    assert isinstance(annotations[1], PDAnnotationLink)

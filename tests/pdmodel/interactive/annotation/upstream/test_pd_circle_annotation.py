"""Ported from pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
annotation/PDCircleAnnotationTest.java (PDFBox 3.0.x)."""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationCircle


def test_create_default_circle_annotation() -> None:
    annotation = PDAnnotationCircle()
    assert annotation.get_cos_object().get_item(COSName.TYPE) == COSName.get_pdf_name("Annot")  # type: ignore[attr-defined]
    assert (
        annotation.get_cos_object().get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        == PDAnnotationCircle.SUB_TYPE
    )

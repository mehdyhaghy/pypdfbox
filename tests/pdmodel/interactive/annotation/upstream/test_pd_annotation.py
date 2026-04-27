"""Ported from pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
annotation/PDAnnotationTest.java (PDFBox 3.0.x).

Upstream's PDAnnotationTest covers PDAnnotationWidget construction, both
the default constructor and the round-trip via
``PDTextField.getWidgets()``.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDTextField


def test_create_default_widget_annotation() -> None:
    annotation: PDAnnotation = PDAnnotationWidget()
    assert annotation.get_subtype() == PDAnnotationWidget.SUB_TYPE
    assert annotation.get_cos_object().get_item(
        COSName.get_pdf_name("Type")
    ) == COSName.get_pdf_name("Annot")


def test_create_widget_annotation_from_field() -> None:
    acro_form = PDAcroForm(None)
    text_field = PDTextField(acro_form)
    annotation: PDAnnotation = text_field.get_widgets()[0]
    assert annotation.get_subtype() == PDAnnotationWidget.SUB_TYPE
    assert annotation.get_cos_object().get_item(
        COSName.get_pdf_name("Type")
    ) == COSName.get_pdf_name("Annot")

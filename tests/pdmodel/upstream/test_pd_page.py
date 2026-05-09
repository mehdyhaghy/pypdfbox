"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPage.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import io

from pypdfbox import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDTextField


def test_adding_page_after_creating_annotation() -> None:
    output = io.BytesIO()
    document = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        acro_form = PDAcroForm(document)
        document.get_document_catalog().set_acro_form(acro_form)

        text_field = PDTextField(acro_form)
        text_field.set_partial_name("testField")
        widget = text_field.get_widgets()[0]
        widget.set_rectangle(PDRectangle.from_xywh(100, 700, 200, 20))
        widget.set_page(page)

        page.set_annotations([widget])
        acro_form.set_fields([text_field])

        document.add_page(page)
        document.save(output)

        assert output.getvalue()
    finally:
        document.close()


def test_null_thread_beads() -> None:
    page = PDPage()

    assert page.get_thread_beads() == []

    page.set_thread_beads([])
    assert page.get_thread_beads() == []

    page.set_thread_beads(None)
    assert page.get_thread_beads() == []

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName
from tests.pdmodel.interactive.form import test_pd_acro_form_flatten as flatten_tests


def test_skipped_widget_assertion_visits_existing_empty_xobjects(
    monkeypatch: Any,
) -> None:
    original_make_document = flatten_tests._make_document_with_form

    def _make_document_with_empty_xobjects() -> Any:
        doc, form = original_make_document()
        page = next(iter(doc.get_pages()))
        resources = COSDictionary()
        resources.set_item(COSName.get_pdf_name("XObject"), COSDictionary())
        page.get_cos_object().set_item(COSName.get_pdf_name("Resources"), resources)
        return doc, form

    monkeypatch.setattr(
        flatten_tests,
        "_make_document_with_form",
        _make_document_with_empty_xobjects,
    )

    flatten_tests.test_flatten_widget_without_appearance_is_skipped_no_error()

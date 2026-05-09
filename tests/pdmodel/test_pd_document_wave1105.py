from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from tests.pdmodel import test_pd_document_wave576


def test_wave1105_signature_helper_removes_existing_fields_array(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def document_with_existing_acro_form() -> PDDocument:
        doc = PDDocument()
        doc.get_document_catalog().set_acro_form(PDAcroForm(doc))
        return doc

    monkeypatch.setattr(
        test_pd_document_wave576,
        "PDDocument",
        document_with_existing_acro_form,
    )

    test_pd_document_wave576.test_wave576_add_signature_creates_fields_array_when_missing()

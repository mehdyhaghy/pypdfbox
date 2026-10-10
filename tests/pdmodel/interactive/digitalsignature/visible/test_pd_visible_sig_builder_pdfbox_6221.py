"""PDFBOX-6221 (3.0 branch, unreleased 3.0.9): the visible-signature
AcroForm default appearance uses /Helv instead of /sylfaen."""

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_builder import (
    PDVisibleSigBuilder,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm


def test_create_acro_form_dictionary_uses_helv() -> None:
    with PDDocument() as doc:
        acro_form = PDAcroForm(doc)
        builder = PDVisibleSigBuilder()
        builder.create_acro_form_dictionary(acro_form, object())
        assert acro_form.get_default_appearance() == "/Helv 0 Tf 0 g"
        assert builder.get_structure().get_acro_form_dictionary() is (
            acro_form.get_cos_object()
        )

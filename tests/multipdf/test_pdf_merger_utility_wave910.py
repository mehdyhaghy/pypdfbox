from __future__ import annotations

import tests.multipdf.test_pdf_merger_utility_round_out as round_out
from pypdfbox.cos import COSArray, COSDictionary, COSName


def test_wave910_exploding_acro_form_local_accessors_return_standins() -> None:
    form = round_out._ExplodingAcroForm()

    form_dict = form.get_cos_object()

    assert isinstance(form_dict, COSDictionary)
    assert isinstance(
        form_dict.get_dictionary_object(COSName.get_pdf_name("Fields")),
        COSArray,
    )
    assert form.get_field_tree() == []
    assert form.get_field("missing") is None


def test_wave910_stub_catalog_exposes_acro_form_and_cos_dictionary() -> None:
    form = round_out._ExplodingAcroForm()
    catalog = round_out._StubCatalog(form)

    assert catalog.get_acro_form() is form
    assert isinstance(catalog.get_cos_object(), COSDictionary)

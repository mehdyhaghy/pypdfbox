from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.form import PDTextField
from tests.pdmodel.interactive.form.test_pd_acro_form_flatten import (
    _attach_widget,
    _make_document_with_form,
)


def test_wave956_flatten_skipped_widget_keeps_existing_empty_xobject_dict() -> None:
    doc, form = _make_document_with_form()
    try:
        page = next(iter(doc.get_pages()))

        resources = COSDictionary()
        xobjects = COSDictionary()
        resources.set_item(COSName.get_pdf_name("XObject"), xobjects)
        page.get_cos_object().set_item(COSName.get_pdf_name("Resources"), resources)

        field = PDTextField(form)
        field.set_partial_name("skip_no_appearance")
        _attach_widget(field.get_cos_object(), page, (10.0, 10.0, 60.0, 30.0), None)
        form.set_fields([field])

        form.flatten()

        annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
        assert isinstance(annots, COSArray)
        assert annots.size() == 1
        assert xobjects.size() == 0
    finally:
        doc.close()

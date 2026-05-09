from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDTextField
from tests.pdmodel.interactive.form.test_pd_acro_form_flatten import (
    _attach_widget,
    _make_document_with_form,
    _make_form_xobject,
)


def test_flatten_skipped_widget_preserves_existing_empty_xobject_resources() -> None:
    doc, form = _make_document_with_form()
    page = next(iter(doc.get_pages()))

    resources = COSDictionary()
    xobjects = COSDictionary()
    resources.set_item(COSName.get_pdf_name("XObject"), xobjects)
    page.get_cos_object().set_item(COSName.get_pdf_name("Resources"), resources)

    field = PDTextField(form)
    field.set_partial_name("no_ap")
    _attach_widget(field.get_cos_object(), page, (10.0, 10.0, 30.0, 20.0), None)
    form.set_fields([field])

    form.flatten()

    assert xobjects.size() == 0
    assert doc.get_document_catalog().get_acro_form() is None


def test_select_appearance_stream_requires_matching_state() -> None:
    widget = COSDictionary()
    ap = COSDictionary()
    states = COSDictionary()
    yes_stream = _make_form_xobject((0.0, 0.0, 10.0, 10.0))
    states.set_item(COSName.get_pdf_name("Yes"), yes_stream)
    ap.set_item(COSName.get_pdf_name("N"), states)
    widget.set_item(COSName.get_pdf_name("AP"), ap)

    form = _make_document_with_form()[1]
    assert form._select_appearance_stream(widget) is None

    widget.set_item(COSName.get_pdf_name("AS"), COSName.get_pdf_name("Off"))
    assert form._select_appearance_stream(widget) is None

    widget.set_item(COSName.get_pdf_name("AS"), COSName.get_pdf_name("Yes"))
    assert form._select_appearance_stream(widget) is yes_stream


def test_resolve_widget_page_falls_back_to_page_annots_scan() -> None:
    _doc, form = _make_document_with_form()
    page = next(iter(form.get_document().get_pages()))  # type: ignore[union-attr]
    widget = COSDictionary()
    annots = COSArray()
    annots.add(widget)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    assert form._resolve_widget_page(widget) is page.get_cos_object()


def test_append_do_to_page_extends_existing_contents_array() -> None:
    _doc, form = _make_document_with_form()
    page = next(iter(form.get_document().get_pages()))  # type: ignore[union-attr]
    existing = COSArray()
    original_stream = COSStream()
    original_stream.set_raw_data(b"q Q\n")
    existing.add(original_stream)
    page.get_cos_object().set_item(COSName.get_pdf_name("Contents"), existing)

    form._append_do_to_page(
        page.get_cos_object(),
        (1.0, 0.0, 0.0, 1.0, 5.0, 6.0),
        COSName.get_pdf_name("FmExisting"),
    )

    assert existing.size() == 2
    assert page.get_contents().endswith(b"/FmExisting Do Q\n")

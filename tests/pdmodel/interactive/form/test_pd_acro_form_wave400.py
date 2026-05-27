from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDFieldStub,
    PDNonTerminalField,
    PDTextField,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


def _num_array(*values: float) -> COSArray:
    arr = COSArray()
    for value in values:
        arr.add(COSFloat(value))
    return arr


def _form_xobject(
    bbox: tuple[float, float, float, float] | None = (0.0, 0.0, 10.0, 10.0),
    matrix: tuple[float, float, float, float, float, float] | None = None,
) -> COSStream:
    stream = COSStream()
    if bbox is not None:
        stream.set_item("BBox", _num_array(*bbox))
    if matrix is not None:
        stream.set_item("Matrix", _num_array(*matrix))
    stream.set_raw_data(b"q Q\n")
    return stream


def _widget(
    page: COSDictionary | None,
    appearance: COSStream | None = None,
    rect: tuple[float, float, float, float] | None = (1.0, 2.0, 11.0, 12.0),
) -> COSDictionary:
    widget = COSDictionary()
    if rect is not None:
        widget.set_item("Rect", _num_array(*rect))
    if page is not None:
        widget.set_item("P", page)
    if appearance is not None:
        ap = COSDictionary()
        ap.set_item("N", appearance)
        widget.set_item("AP", ap)
    return widget


def test_wave400_constructor_with_existing_dictionary_and_document_accessors() -> None:
    dictionary = COSDictionary()
    document = object()
    form = PDAcroForm(document, dictionary)

    assert form.get_cos_object() is dictionary
    assert form.get_dictionary() is dictionary
    assert form.get_document() is document
    assert form.get_fields() == []


def test_wave400_get_fields_skips_non_dictionary_root_entries() -> None:
    fields = COSArray()
    fields.add(COSName.get_pdf_name("not-a-field"))
    field = COSDictionary()
    field.set_string("T", "real")
    fields.add(field)
    dictionary = COSDictionary()
    dictionary.set_item("Fields", fields)
    form = PDAcroForm(dictionary=dictionary)

    assert [item.get_partial_name() for item in form.get_fields()] == ["real"]


def test_wave400_remove_field_returns_false_when_fields_entry_missing() -> None:
    form = PDAcroForm()
    field = PDFieldStub(form)
    form.get_cos_object().remove_item("Fields")

    assert form.remove_field(field) is False


def test_wave400_remove_child_returns_false_when_parent_has_no_kids_array() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    child = PDFieldStub(form)
    child.set_parent(parent)

    assert form.remove_field(child) is False


def test_wave400_presence_predicates_and_clear_helpers_for_optional_entries() -> None:
    form = PDAcroForm()

    form.set_need_appearances(True)
    assert form.has_need_appearances() is True
    form.clear_need_appearances()
    assert form.has_need_appearances() is False

    form.get_cos_object().set_item("DA", COSName.get_pdf_name("NamedAppearance"))
    assert form.get_default_appearance_if_exists() == "NamedAppearance"
    assert form.has_default_appearance() is True
    form.clear_default_appearance()
    assert form.has_default_appearance() is False

    form.set_q(PDAcroForm.QUADDING_RIGHT)
    assert form.has_q() is True
    form.clear_q()
    assert form.has_q() is False

    form.set_default_resources(PDResources())
    assert form.has_default_resources() is True
    form.clear_default_resources()
    assert form.has_default_resources() is False


def test_wave400_get_calc_order_materializes_dictionary_entries() -> None:
    form = PDAcroForm()
    field = PDTextField(form)
    field.set_partial_name("total")
    # /CO is matched against the field tree (upstream parity), so the field
    # must be reachable from /Fields. A non-dictionary /CO entry (the COSName)
    # is skipped exactly as upstream skips it.
    form.set_fields([field])
    calc_order = COSArray()
    calc_order.add(COSName.get_pdf_name("skip"))
    calc_order.add(field.get_cos_object())
    form.get_cos_object().set_item("CO", calc_order)

    assert [item.get_partial_name() for item in form.get_calc_order()] == ["total"]


def test_wave400_flatten_dynamic_xfa_logs_and_returns(caplog: pytest.LogCaptureFixture) -> None:
    form = PDAcroForm()
    form.get_cos_object().set_item("XFA", COSDictionary())

    with caplog.at_level(logging.WARNING):
        form.flatten()

    assert "dynamic XFA" in caplog.text
    assert form.has_xfa() is True


def test_wave400_flatten_empty_targets_returns_without_clearing_xfa() -> None:
    form = PDAcroForm()
    field = PDFieldStub(form)
    form.get_cos_object().set_item("XFA", COSDictionary())

    form.flatten(fields=[])
    form.flatten(fields=[field])

    assert form.has_xfa() is True


def test_wave400_flatten_need_appearances_warning_still_flattens() -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
        doc.add_page(page)
        form = PDAcroForm(doc)
        field = PDTextField(form)
        field.set_partial_name("name")
        widget = _widget(page.get_cos_object(), _form_xobject())
        field.get_cos_object().add_all(widget)
        annots = COSArray()
        annots.add(field.get_cos_object())
        page.get_cos_object().set_item("Annots", annots)
        form.set_fields([field])
        form.set_need_appearances(True)

        form.flatten()

        assert page.get_contents()
    finally:
        doc.close()


def test_wave400_flatten_resolves_page_by_annotation_scan_when_p_is_missing() -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
        doc.add_page(page)
        form = PDAcroForm(doc)
        field = PDTextField(form)
        field.set_partial_name("scanned")
        field.get_cos_object().add_all(_widget(None, _form_xobject()))
        annots = COSArray()
        annots.add(field.get_cos_object())
        page.get_cos_object().set_item("Annots", annots)
        form.set_fields([field])

        form.flatten(fields=[field])

        assert annots.size() == 0
        assert b" Do Q" in page.get_contents()
    finally:
        doc.close()


def test_wave400_flatten_removes_indirect_widget_annotation() -> None:
    page = COSDictionary()
    widget = _widget(page, _form_xobject())
    wrapper = COSObject(10, 0, resolved=widget)
    annots = COSArray()
    annots.add(wrapper)
    page.set_item("Annots", annots)

    PDAcroForm._remove_widget_from_page(page, widget)

    assert annots.size() == 0


def test_wave400_flatten_skips_malformed_widget_geometry() -> None:
    form = PDAcroForm()
    page = COSDictionary()
    widget = _widget(page, _form_xobject(), rect=None)

    form._flatten_widget(widget)
    assert page.get_dictionary_object("Contents") is None

    widget = _widget(page, _form_xobject(bbox=None))
    form._flatten_widget(widget)
    assert page.get_dictionary_object("Contents") is None

    widget = _widget(page, _form_xobject())
    rect = widget.get_dictionary_object("Rect")
    assert isinstance(rect, COSArray)
    rect.set(0, COSName.get_pdf_name("bad"))
    form._flatten_widget(widget)
    assert page.get_dictionary_object("Contents") is None


def test_wave400_select_appearance_state_dict_requires_matching_as() -> None:
    normal = COSDictionary()
    normal.set_item("Yes", _form_xobject())
    ap = COSDictionary()
    ap.set_item("N", normal)
    widget = COSDictionary()
    widget.set_item("AP", ap)

    assert PDAcroForm._select_appearance_stream(widget) is None
    widget.set_item("AS", COSName.get_pdf_name("Off"))
    assert PDAcroForm._select_appearance_stream(widget) is None


def test_wave400_form_geometry_uses_valid_matrix_and_ignores_bad_matrix() -> None:
    stream = _form_xobject(matrix=(2.0, 0.0, 0.0, 2.0, 5.0, 7.0))
    bbox, matrix = PDAcroForm._read_form_geometry(stream)
    assert bbox == (0.0, 0.0, 10.0, 10.0)
    assert matrix == (2.0, 0.0, 0.0, 2.0, 5.0, 7.0)

    bad_matrix = COSArray()
    bad_matrix.add(COSName.get_pdf_name("bad"))
    for _ in range(5):
        bad_matrix.add(COSFloat(0.0))
    stream.set_item("Matrix", bad_matrix)

    assert PDAcroForm._read_form_geometry(stream)[1] == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_wave400_append_do_to_page_appends_to_existing_contents_array() -> None:
    page = COSDictionary()
    contents = COSArray()
    existing = COSStream()
    existing.set_raw_data(b"existing")
    contents.add(existing)
    page.set_item("Contents", contents)

    PDAcroForm._append_do_to_page(
        page, (1.25, 0.0, 0.0, 1.0, 2.5, 0.0), COSName.get_pdf_name("Fm7")
    )

    assert contents.size() == 2
    appended = contents.get_object(1)
    assert isinstance(appended, COSStream)
    assert b"1.25 0 0 1 2.5 0 cm /Fm7 Do" in appended.get_raw_data()

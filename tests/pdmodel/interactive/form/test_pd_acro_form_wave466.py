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
    COSString,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDNonTerminalField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField


def _num_array(*values: float) -> COSArray:
    return COSArray([COSFloat(value) for value in values])


def _appearance(
    bbox: tuple[float, float, float, float] | None = (0.0, 0.0, 10.0, 10.0),
) -> COSStream:
    stream = COSStream()
    if bbox is not None:
        stream.set_item("BBox", _num_array(*bbox))
    stream.set_raw_data(b"q Q\n")
    return stream


def test_wave466_get_default_appearance_if_exists_accepts_cos_string() -> None:
    form = PDAcroForm()
    form.get_cos_object().set_item("DA", COSString("/F1 9 Tf 0 g"))

    assert form.get_default_appearance_if_exists() == "/F1 9 Tf 0 g"
    assert form.has_default_appearance() is True


def test_wave466_get_q_if_exists_ignores_malformed_value() -> None:
    form = PDAcroForm()
    form.get_cos_object().set_item("Q", COSName.get_pdf_name("Center"))

    assert form.get_q_if_exists() is None
    assert form.has_q() is False
    assert form.get_q() == PDAcroForm.QUADDING_LEFT


def test_wave466_collect_terminals_logs_and_stops_on_cycle(
    caplog: pytest.LogCaptureFixture,
) -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("parent")
    child = PDNonTerminalField(form)
    child.set_partial_name("child")
    parent.get_cos_object().set_item("Kids", COSArray([child.get_cos_object()]))
    child.get_cos_object().set_item("Kids", COSArray([parent.get_cos_object()]))

    with caplog.at_level(logging.ERROR):
        assert form._collect_terminals(parent) == []  # noqa: SLF001

    assert "ignored to avoid recursion" in caplog.text


def test_wave466_select_appearance_stream_handles_direct_and_state_dict() -> None:
    direct = _appearance()
    ap = COSDictionary()
    ap.set_item("N", direct)
    widget = COSDictionary()
    widget.set_item("AP", ap)
    assert PDAcroForm._select_appearance_stream(widget) is direct  # noqa: SLF001

    selected = _appearance()
    normal = COSDictionary()
    normal.set_item("Yes", selected)
    ap.set_item("N", normal)
    widget.set_item("AS", COSName.get_pdf_name("Yes"))
    assert PDAcroForm._select_appearance_stream(widget) is selected  # noqa: SLF001


def test_wave466_resolve_widget_page_returns_none_without_document() -> None:
    widget = COSDictionary()
    widget.set_item("P", COSName.get_pdf_name("NotAPage"))

    assert PDAcroForm()._resolve_widget_page(widget) is None  # noqa: SLF001
    assert PDAcroForm(object())._resolve_widget_page(widget) is None  # noqa: SLF001


def test_wave466_read_rect_normalizes_reversed_corners() -> None:
    rect = _num_array(20.0, 10.0, 5.0, 30.0)

    assert PDAcroForm._read_rect(rect) == (5.0, 10.0, 20.0, 30.0)  # noqa: SLF001


def test_wave466_read_form_geometry_rejects_malformed_bbox() -> None:
    stream = _appearance(bbox=None)
    stream.set_item("BBox", COSArray([COSFloat(0.0), COSName.get_pdf_name("bad")]))

    bbox, matrix = PDAcroForm._read_form_geometry(stream)  # noqa: SLF001

    assert bbox is None
    assert matrix == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_wave466_compute_ctm_handles_zero_sized_transformed_bbox() -> None:
    assert PDAcroForm._compute_ctm(  # noqa: SLF001
        (10.0, 20.0, 30.0, 50.0),
        (0.0, 0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0, 1.0, 5.0, 7.0),
    ) == (20.0, 0.0, 0.0, 30.0, -90.0, -190.0)


def test_wave466_add_xobject_skips_existing_names_and_creates_resources() -> None:
    page = COSDictionary()
    form_xobject = _appearance()

    first_name = PDAcroForm._add_xobject_to_page(page, _appearance())  # noqa: SLF001
    second_name = PDAcroForm._add_xobject_to_page(page, form_xobject)  # noqa: SLF001

    assert first_name.name == "Fm0"
    assert second_name.name == "Fm1"
    resources = page.get_dictionary_object("Resources")
    assert isinstance(resources, COSDictionary)
    xobjects = resources.get_dictionary_object("XObject")
    assert isinstance(xobjects, COSDictionary)
    assert xobjects.get_dictionary_object("Fm1") is form_xobject


def test_wave466_append_do_to_page_promotes_single_stream_to_array() -> None:
    page = COSDictionary()
    existing = COSStream()
    existing.set_raw_data(b"existing")
    page.set_item("Contents", existing)

    PDAcroForm._append_do_to_page(  # noqa: SLF001
        page, (1.0, 0.0, 0.0, 2.0, 3.0, 4.0), COSName.get_pdf_name("Fm9")
    )

    contents = page.get_dictionary_object("Contents")
    assert isinstance(contents, COSArray)
    assert contents.get_object(0) is existing
    appended = contents.get_object(1)
    assert isinstance(appended, COSStream)
    assert b"/Fm9 Do Q" in appended.get_raw_data()


def test_wave466_remove_widget_from_page_handles_missing_annots() -> None:
    page = COSDictionary()
    widget = COSDictionary()

    PDAcroForm._remove_widget_from_page(page, widget)  # noqa: SLF001

    assert page.get_dictionary_object("Annots") is None


def test_wave466_partial_flatten_removes_direct_terminal_root_only() -> None:
    page = COSDictionary()
    widget = COSDictionary()
    widget.set_item("P", page)
    widget.set_item("Rect", _num_array(0.0, 0.0, 10.0, 10.0))
    ap = COSDictionary()
    ap.set_item("N", _appearance())
    widget.set_item("AP", ap)
    form = PDAcroForm()
    keep = PDTextField(form)
    keep.set_partial_name("keep")
    drop = PDTextField(form)
    drop.set_partial_name("drop")
    drop.get_cos_object().add_all(widget)
    annots = COSArray([COSObject(20, 0, resolved=drop.get_cos_object())])
    page.set_item("Annots", annots)
    form.set_fields([keep, drop])

    form.flatten(fields=[drop])

    assert [field.get_partial_name() for field in form.get_fields()] == ["keep"]
    assert annots.size() == 0
    assert form.get_cos_object().contains_key("Fields")
 

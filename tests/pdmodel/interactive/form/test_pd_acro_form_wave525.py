from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import (
    PDAcroForm,
    PDFieldStub,
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_xfa_resource import PDXFAResource


def test_wave525_append_field_subtree_walks_non_terminal_children() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("parent")
    child = PDFieldStub(form)
    child.set_partial_name("child")
    parent.set_children([child])
    out = []

    form._append_field_subtree(parent, out)  # noqa: SLF001

    assert [field.get_fully_qualified_name() for field in out] == [
        "parent",
        "parent.child",
    ]


def test_wave525_append_only_aliases_preserve_existing_signature_bits() -> None:
    form = PDAcroForm()
    form.set_signature_flags(0x80 | PDAcroForm.FLAG_SIGNATURES_EXIST)

    form.set_append_only(True)

    assert form.is_append_only() is True
    assert form.get_signature_flags() == (
        0x80 | PDAcroForm.FLAG_SIGNATURES_EXIST | PDAcroForm.FLAG_APPEND_ONLY
    )


def test_wave525_calc_order_missing_clear_and_round_trip() -> None:
    form = PDAcroForm()
    field = PDFieldStub(form)
    field.set_partial_name("amount")

    assert form.get_calc_order() == []
    form.set_calc_order([field])
    assert form.has_calc_order() is True
    assert [item.get_partial_name() for item in form.get_calc_order()] == ["amount"]

    form.clear_calc_order()

    assert form.has_calc_order() is False
    assert form.get_cos_object().contains_key("CO") is False


def test_wave525_scripting_handler_round_trips_opaque_object() -> None:
    form = PDAcroForm()
    handler = object()

    assert form.get_scripting_handler() is None
    form.set_scripting_handler(handler)
    assert form.get_scripting_handler() is handler
    form.set_scripting_handler(None)
    assert form.get_scripting_handler() is None


def test_wave525_deferred_fdf_methods_raise_not_implemented() -> None:
    form = PDAcroForm()

    with pytest.raises(NotImplementedError, match="import_fdf"):
        form.import_fdf(object())
    with pytest.raises(NotImplementedError, match="export_fdf"):
        form.export_fdf()


def test_wave525_xfa_accessor_alias_and_clear() -> None:
    form = PDAcroForm()
    stream = COSStream()
    stream.set_raw_data(b"<xdp />")
    xfa = PDXFAResource(stream)

    assert form.get_xfa() is None
    form.set_xfa(xfa)
    assert form.has_xfa() is True
    assert form.get_xfa().get_cos_object() is stream

    form.clear_xfa()

    assert form.has_xfa() is False
    assert form.xfa() is None


def test_wave525_flatten_returns_when_requested_subtree_has_no_terminals() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("empty")
    form.set_fields([parent])

    form.flatten(fields=[parent])

    assert [field.get_partial_name() for field in form.get_fields()] == ["empty"]


def test_wave525_flatten_widget_skips_missing_page_after_valid_appearance() -> None:
    form = PDAcroForm()
    appearance = COSStream()
    appearance.set_item("BBox", COSArray())
    ap = COSDictionary()
    ap.set_item("N", appearance)
    widget = COSDictionary()
    widget.set_item("AP", ap)
    widget.set_item("Rect", COSArray())

    form._flatten_widget(widget)  # noqa: SLF001

    assert widget.get_dictionary_object("AP") is ap


def test_wave525_select_appearance_requires_appearance_dictionary() -> None:
    widget = COSDictionary()
    widget.set_item("AP", COSName.get_pdf_name("not-a-dictionary"))

    assert PDAcroForm._select_appearance_stream(widget) is None  # noqa: SLF001


def test_wave525_resolve_widget_page_scans_past_malformed_annots() -> None:
    form = PDAcroForm(object())
    widget = COSDictionary()

    assert form._resolve_widget_page(widget) is None  # noqa: SLF001
    form._remove_acro_form_from_catalog()  # noqa: SLF001

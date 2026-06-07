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
    # /CO is matched against the field tree (upstream parity — getCalcOrder
    # only returns /CO fields reachable from /Fields), so add the field as a
    # root field before driving the round trip.
    form.set_fields([field])
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


def test_wave525_fdf_round_trip_methods_implemented() -> None:
    """``import_fdf`` and ``export_fdf`` are wired now — verify the
    happy path returns the right shape rather than the previous
    ``NotImplementedError`` placeholder."""
    from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument

    form = PDAcroForm()

    with pytest.raises(TypeError):
        form.import_fdf(object())

    fdf = form.export_fdf()
    assert isinstance(fdf, FDFDocument)
    # No fields → /FDF has no /Fields entry (upstream omits the array
    # when empty; see PDAcroForm.exportFDF lines 168-171).
    assert fdf.get_catalog().get_fdf().get_fields() is None


def test_wave525_import_fdf_applies_field_values() -> None:
    """``PDAcroForm.import_fdf`` should look each FDF field up by partial
    name and delegate to the matching :class:`PDField`'s ``import_fdf``."""
    from pypdfbox.cos import COSString
    from pypdfbox.pdmodel.fdf.fdf_dictionary import FDFDictionary
    from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument
    from pypdfbox.pdmodel.fdf.fdf_field import FDFField
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

    form = PDAcroForm()
    field = PDTextField(form)
    field.set_partial_name("name")
    form.set_fields([field])

    fdf_doc = FDFDocument()
    fdf_field = FDFField()
    fdf_field.set_partial_field_name("name")
    fdf_field.set_value(COSString("hello"))
    fdf_dict = FDFDictionary()
    fdf_dict.set_fields([fdf_field])
    fdf_doc.get_catalog().set_fdf(fdf_dict)

    form.import_fdf(fdf_doc)
    assert field.get_value() == "hello"


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


def test_wave525_flatten_removes_requested_field_even_with_no_terminals() -> None:
    # Upstream PDAcroForm.flatten(fields, ...) ends in removeFields(fields),
    # which removes every *passed* field from its array regardless of whether
    # any widget was rendered. A childless non-terminal passed to flatten is
    # therefore dropped from the root /Fields (wave 1506, agent C — the prior
    # port left it behind, which diverged from upstream removeFields).
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("empty")
    form.set_fields([parent])

    form.flatten(fields=[parent])

    assert form.get_fields() == []


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

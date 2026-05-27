"""Parity tests for upstream-named ``PDAcroForm`` accessors.

Covers the surface added on top of the wave-19 lite form: ``/DA``, ``/Q``,
``/SigFlags`` (per-bit accessors), ``/NeedAppearances``, ``/DR``, plus the
deferred ``refresh_appearances`` / ``import_fdf`` placeholders.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDFieldStub
from pypdfbox.pdmodel.pd_resources import PDResources


def test_default_appearance_round_trip() -> None:
    form = PDAcroForm()
    # Upstream returns "" (not None) when /DA is absent.
    assert form.get_default_appearance() == ""

    form.set_default_appearance("/Helv 0 Tf 0 g")
    assert form.get_default_appearance() == "/Helv 0 Tf 0 g"

    form.set_default_appearance("")
    assert form.get_default_appearance() == ""


def test_q_default_zero_and_round_trip() -> None:
    form = PDAcroForm()
    assert form.get_q() == 0  # default = quad-left

    for value in (0, 1, 2):
        form.set_q(value)
        assert form.get_q() == value


def test_signatures_exist_and_append_only_round_trip_via_sig_flags() -> None:
    form = PDAcroForm()
    assert form.is_signatures_exist() is False
    assert form.is_append_only() is False

    form.set_signatures_exist(True)
    assert form.is_signatures_exist() is True
    assert form.is_append_only() is False
    # Bit-level: only bit 1 should be set after toggling /SignaturesExist.
    assert form.get_cos_object().get_int(COSName.get_pdf_name("SigFlags")) == 1

    form.set_append_only(True)
    assert form.is_signatures_exist() is True
    assert form.is_append_only() is True
    assert form.get_cos_object().get_int(COSName.get_pdf_name("SigFlags")) == 3

    # Clearing /SignaturesExist must preserve /AppendOnly.
    form.set_signatures_exist(False)
    assert form.is_signatures_exist() is False
    assert form.is_append_only() is True
    assert form.get_cos_object().get_int(COSName.get_pdf_name("SigFlags")) == 2

    form.set_append_only(False)
    assert form.is_append_only() is False
    assert form.get_cos_object().get_int(COSName.get_pdf_name("SigFlags")) == 0


def test_need_appearances_default_false_and_round_trip() -> None:
    form = PDAcroForm()
    assert form.is_need_appearances() is False

    form.set_need_appearances(True)
    assert form.is_need_appearances() is True

    form.set_need_appearances(False)
    assert form.is_need_appearances() is False


def test_refresh_appearances_no_args_walks_field_tree_no_op() -> None:
    """Empty form: refresh_appearances is a successful no-op (no
    terminal fields → nothing to construct)."""
    form = PDAcroForm()
    form.refresh_appearances()  # must not raise


def test_refresh_appearances_with_field_list_walks_supplied_fields() -> None:
    """Supplied terminal fields: refresh_appearances dispatches into
    each terminal's ``construct_appearances`` (lite no-op debug log;
    must not raise)."""
    form = PDAcroForm()
    field = PDFieldStub(form)
    field.set_partial_name("name")
    form.set_fields([field])
    form.refresh_appearances([field])  # must not raise


def test_import_fdf_rejects_non_fdf_document() -> None:
    form = PDAcroForm()
    with pytest.raises(TypeError):
        form.import_fdf(object())


def _value_string(field: PDFieldStub) -> str | None:
    """Read the field's ``/V`` entry as a Python string (stub fields
    don't expose a typed ``get_value`` accessor)."""
    v = field.get_cos_object().get_string(COSName.get_pdf_name("V"))
    return v


def test_import_xfdf_from_bytes_loads_and_imports() -> None:
    """``PDAcroForm.import_xfdf`` accepts raw XFDF bytes, parses them via
    :meth:`Loader.load_xfdf`, and forwards to :meth:`import_fdf`."""
    form = PDAcroForm()
    field = PDFieldStub(form)
    field.set_partial_name("city")
    form.set_fields([field])
    sample = (
        b'<?xml version="1.0"?>'
        b'<xfdf><fields>'
        b'<field name="city"><value>Lyon</value></field>'
        b"</fields></xfdf>"
    )
    form.import_xfdf(sample)
    assert _value_string(field) == "Lyon"


def test_import_xfdf_from_fdf_document_short_circuits() -> None:
    """Passing an already-loaded FDFDocument re-uses it without re-parsing."""
    from pypdfbox.pdmodel.fdf import FDFDocument

    form = PDAcroForm()
    field = PDFieldStub(form)
    field.set_partial_name("city")
    form.set_fields([field])
    fdf = FDFDocument()
    fdf.set_xfdf(
        b'<?xml version="1.0"?>'
        b'<xfdf><fields>'
        b'<field name="city"><value>Marseille</value></field>'
        b"</fields></xfdf>"
    )
    try:
        form.import_xfdf(fdf)
    finally:
        fdf.close()
    assert _value_string(field) == "Marseille"


def test_export_fdf_returns_empty_fdf_document() -> None:
    """Exporting a fresh, empty form yields a freshly-built FDFDocument
    whose ``/FDF`` dictionary carries no fields."""
    from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument

    form = PDAcroForm()
    fdf = form.export_fdf()
    assert isinstance(fdf, FDFDocument)
    assert fdf.get_catalog().get_fdf().get_fields() is None


def test_default_resources_default_none_and_round_trip() -> None:
    form = PDAcroForm()
    assert form.get_default_resources() is None

    resources = PDResources()
    form.set_default_resources(resources)

    fetched = form.get_default_resources()
    assert fetched is not None
    # Round-trip preserves the same backing /Resources COSDictionary.
    assert fetched.get_cos_object() is resources.get_cos_object()
    # /DR is now set on the form dictionary.
    assert (
        form.get_cos_object().get_dictionary_object(COSName.get_pdf_name("DR"))
        is resources.get_cos_object()
    )

    # Setting None removes the entry.
    form.set_default_resources(None)
    assert form.get_default_resources() is None
    assert form.get_cos_object().get_dictionary_object(COSName.get_pdf_name("DR")) is None


def test_calc_order_default_empty_and_round_trip() -> None:
    form = PDAcroForm()
    assert form.get_calc_order() == []

    field = PDFieldStub(form, COSDictionary(), None)
    field.set_partial_name("a")
    # /CO entries are matched against the field tree (upstream parity —
    # getCalcOrder only returns /CO fields reachable from /Fields), so the
    # field must be a root field for get_calc_order to surface it.
    form.set_fields([field])
    form.set_calc_order([field])

    co = form.get_calc_order()
    assert len(co) == 1
    assert co[0].get_cos_object() is field.get_cos_object()

    # Empty list / None clears the entry.
    form.set_calc_order(None)
    assert form.get_calc_order() == []
    assert form.get_cos_object().get_dictionary_object(COSName.get_pdf_name("CO")) is None


def test_get_xfa_alias_matches_xfa() -> None:
    form = PDAcroForm()
    # No /XFA → both accessors agree on None.
    assert form.get_xfa() is None
    assert form.xfa() is None

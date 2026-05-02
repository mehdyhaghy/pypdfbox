"""Hand-written parity tests for the ``PDPushButton`` round-out (Wave 201).

Targets small remaining gaps on the push-button subclass surface:

- ``FLAG_PUSHBUTTON`` bit value parity with PDF 32000-1 §12.7.4.2.1 Table 226.
- Read-side overrides: ``get_value`` / ``get_default_value`` / ``get_value_as_string``
  return ``""`` even when ``/V`` or ``/DV`` are populated on the underlying
  dictionary (upstream parity — push buttons hold no value).
- ``get_on_values`` returns an empty set even when widgets carry an ``/AP /N``
  with on-state names (upstream parity — push buttons have no toggle states).
- ``get_export_values`` returns an empty list even when ``/Opt`` is populated
  on the underlying dictionary.
- ``set_export_values`` rejects non-empty input but accepts ``None`` and
  ``[]`` cleanly (no /Opt residue).
- ``construct_appearances`` is a no-op (mirrors upstream TODO).
- Loading a ``PDPushButton`` from an existing dictionary preserves its
  ``/Ff`` bits — the constructor must not retroactively force
  ``FLAG_PUSHBUTTON`` on existing fields.
- ``regenerate_appearance`` dispatches through the shared
  :class:`PDAppearanceGenerator`.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton

_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_OPT: COSName = COSName.get_pdf_name("Opt")
_KIDS: COSName = COSName.get_pdf_name("Kids")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")


# ---------- FLAG_PUSHBUTTON bit value parity ----------


def test_push_button_flag_value_matches_pdf_spec() -> None:
    """PDF 32000-1 §12.7.4.2.1 Table 226: bit 17 (1 << 16) — Pushbutton."""
    assert PDButton.FLAG_PUSHBUTTON == 1 << 16
    # Inheritance: PDPushButton inherits the same constant from PDButton.
    assert PDPushButton.FLAG_PUSHBUTTON == 1 << 16


def test_push_button_fresh_field_has_pushbutton_flag_set() -> None:
    """Fresh PDPushButton sets /Ff bit 17 — upstream ``PDPushButton(PDAcroForm)``
    invokes ``getCOSObject().setFlag(COSName.FF, FLAG_PUSHBUTTON, true)``."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    flags = pb.get_field_flags()
    assert flags & PDPushButton.FLAG_PUSHBUTTON
    # And FLAG_RADIO is not collaterally set (the type bits are mutually exclusive).
    assert not (flags & PDButton.FLAG_RADIO)


# ---------- read-side overrides (value-less semantics) ----------


def test_push_button_get_value_returns_empty_even_when_v_set() -> None:
    """Push buttons hold no value — even if ``/V`` is somehow populated on the
    raw dict, ``get_value()`` returns ``""`` (upstream parity)."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    pb.get_cos_object().set_name(_V, "Ignored")
    assert pb.get_value() == ""


def test_push_button_get_default_value_returns_empty_even_when_dv_set() -> None:
    """``getDefaultValue()`` upstream returns ``""`` unconditionally — verify
    even a populated ``/DV`` does not leak through."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    pb.get_cos_object().set_name(_DV, "Ignored")
    assert pb.get_default_value() == ""


def test_push_button_get_value_as_string_mirrors_get_value() -> None:
    """Upstream: ``getValueAsString()`` returns ``getValue()`` — both empty."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    pb.get_cos_object().set_name(_V, "Anything")
    assert pb.get_value_as_string() == pb.get_value()
    assert pb.get_value_as_string() == ""


# ---------- /Opt + export-value handling ----------


def test_push_button_get_export_values_empty_even_when_opt_populated() -> None:
    """Upstream: ``getExportValues()`` returns ``Collections.emptyList()`` —
    even a populated ``/Opt`` array does not leak through."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    pb.get_cos_object().set_item(_OPT, COSArray.of_cos_strings(["a", "b"]))
    assert pb.get_export_values() == []


def test_push_button_set_export_values_none_is_no_op_no_opt_written() -> None:
    """``setExportValues(None)`` upstream falls through to the parent which
    removes ``/Opt`` — must not write an empty array."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    pb.set_export_values(None)
    assert _OPT not in pb.get_cos_object()


def test_push_button_set_export_values_empty_list_clears_opt() -> None:
    """``setExportValues([])`` upstream is a tolerated no-op — and the
    inherited PDButton path removes any pre-existing ``/Opt``."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    # Pre-seed /Opt directly on the dict, bypassing the rejecting setter.
    pb.get_cos_object().set_item(_OPT, COSArray.of_cos_strings(["x"]))
    pb.set_export_values([])
    assert _OPT not in pb.get_cos_object()


def test_push_button_set_export_values_rejects_with_message() -> None:
    """Upstream raises ``IllegalArgumentException`` with this exact message
    when callers try to write a non-empty Opt to a push button."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    with pytest.raises(ValueError) as excinfo:
        pb.set_export_values(["a", "b"])
    assert "shall not use the Opt" in str(excinfo.value)


# ---------- get_on_values is empty ----------


def test_push_button_get_on_values_empty_even_with_widget_appearance() -> None:
    """Upstream: ``getOnValues()`` returns ``Collections.emptySet()``. Push
    buttons do not have on-states; even a widget with ``/AP /N /Yes`` must not
    contribute."""
    form = PDAcroForm()
    pb = PDPushButton(form)

    # Build a widget with /AP /N /Yes and attach it as a kid of the field.
    widget_dict = COSDictionary()
    widget_dict.set_name(COSName.get_pdf_name("Type"), "Annot")
    widget_dict.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    n_dict = COSDictionary()
    n_dict.set_item(COSName.get_pdf_name("Yes"), COSDictionary())
    ap_dict = COSDictionary()
    ap_dict.set_item(_N, n_dict)
    widget_dict.set_item(_AP, ap_dict)

    kids = COSArray()
    kids.add(widget_dict)
    pb.get_cos_object().set_item(_KIDS, kids)

    assert pb.get_on_values() == set()


# ---------- construct_appearances is a no-op ----------


def test_push_button_construct_appearances_does_not_mutate_dict() -> None:
    """Upstream: ``constructAppearances`` is a TODO no-op. Verify it does not
    add ``/AS`` to widgets or otherwise mutate the field."""
    form = PDAcroForm()
    pb = PDPushButton(form)

    # Resolve widgets first — get_widgets() promotes the field dict to a
    # widget (Type/Subtype) on a fresh terminal field. Snapshot AFTER that
    # promotion so we're measuring construct_appearances side effects only.
    widget = pb.get_widgets()[0]
    field_before = list(pb.get_cos_object().key_set())
    widget_before = list(widget.get_cos_object().key_set())

    result = pb.construct_appearances()
    assert result is None
    assert list(pb.get_cos_object().key_set()) == field_before
    assert list(widget.get_cos_object().key_set()) == widget_before
    # Specifically, no /AS got synthesised on the widget.
    assert COSName.get_pdf_name("AS") not in widget.get_cos_object()


# ---------- existing-dict ctor preserves /Ff ----------


def test_push_button_from_existing_dict_preserves_flags_no_force() -> None:
    """Loading PDPushButton from a saved dict must NOT stomp /Ff. The ctor's
    ``new_field`` branch only fires for fresh fields — callers that wrap a
    pre-existing /Btn dictionary with the pushbutton bit cleared still get
    back exactly what is on disk."""
    field = COSDictionary()
    field.set_name(_FT, "Btn")
    # Pre-existing flags: pushbutton + read-only.
    pre_flags = PDButton.FLAG_PUSHBUTTON | (1 << 0)  # bit 1 == ReadOnly
    field.set_int(_FF, pre_flags)

    form = PDAcroForm()
    pb = PDPushButton(form, field=field)
    assert pb.get_field_flags() == pre_flags
    assert pb.is_push_button() is True


def test_push_button_from_existing_dict_without_pushbutton_bit_preserved() -> None:
    """Even an inconsistent existing dict (Btn + no FLAG_PUSHBUTTON) is
    preserved verbatim — the ctor must not retroactively force the bit."""
    field = COSDictionary()
    field.set_name(_FT, "Btn")
    field.set_int(_FF, 0)

    form = PDAcroForm()
    pb = PDPushButton(form, field=field)
    assert pb.get_field_flags() == 0
    assert pb.is_push_button() is False


# ---------- regenerate_appearance dispatch ----------


def test_push_button_regenerate_appearance_calls_appearance_generator() -> None:
    """Verify ``regenerate_appearance`` routes through ``PDAppearanceGenerator.generate``."""
    from pypdfbox.pdmodel.interactive.form import pd_appearance_generator

    form = PDAcroForm()
    pb = PDPushButton(form)

    calls: list[object] = []
    original = pd_appearance_generator.PDAppearanceGenerator.generate

    def tracker(self, field):  # noqa: ANN001 — local monkeypatch
        calls.append(field)

    pd_appearance_generator.PDAppearanceGenerator.generate = tracker  # type: ignore[assignment]
    try:
        pb.regenerate_appearance()
    finally:
        pd_appearance_generator.PDAppearanceGenerator.generate = original  # type: ignore[assignment]

    assert calls == [pb]


# ---------- PDButton.set_push_button(False) flips the type ----------


def test_push_button_set_push_button_false_clears_flag() -> None:
    """``set_push_button(False)`` clears the type bit — even though the
    PDPushButton subclass instance still keeps its Python identity, the
    underlying field becomes a generic /Btn after the flag flip."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    assert pb.is_push_button() is True
    pb.set_push_button(False)
    assert pb.is_push_button() is False
    # And the radio bit is not flipped on as a side effect.
    assert pb.is_radio_button() is False


# ---------- widgets surface ----------


def test_push_button_get_widgets_returns_self_widget_for_fresh_field() -> None:
    """Fresh PDPushButton has the field dict double as its single widget
    (no /Kids) — upstream PDTerminalField.getWidgets fallback path."""
    form = PDAcroForm()
    pb = PDPushButton(form)
    widgets = pb.get_widgets()
    assert len(widgets) == 1
    assert isinstance(widgets[0], PDAnnotationWidget)
    # The widget wraps the same COS dictionary as the field.
    assert widgets[0].get_cos_object() is pb.get_cos_object()


# ---------- /V on inheritance chain still suppressed ----------


def test_push_button_get_value_ignores_inherited_v_from_parent() -> None:
    """Even if a parent non-terminal field carries ``/V``, push button
    overrides ``get_value`` to return ``""`` unconditionally."""
    parent_dict = COSDictionary()
    parent_dict.set_name(_FT, "Btn")
    parent_dict.set_name(_V, "Inherited")

    child_dict = COSDictionary()
    child_dict.set_int(_FF, PDButton.FLAG_PUSHBUTTON)
    child_dict.set_item(COSName.get_pdf_name("Parent"), parent_dict)

    form = PDAcroForm()
    pb = PDPushButton(form, field=child_dict)
    assert pb.get_value() == ""
    assert pb.get_default_value() == ""
    assert pb.get_value_as_string() == ""

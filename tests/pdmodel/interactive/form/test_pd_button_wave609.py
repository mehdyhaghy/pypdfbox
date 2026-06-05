from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

_AP = COSName.get_pdf_name("AP")
_DV = COSName.get_pdf_name("DV")
_FT = COSName.get_pdf_name("FT")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_OPT = COSName.get_pdf_name("Opt")
_V = COSName.get_pdf_name("V")


def _normal_appearance(*states: str) -> COSDictionary:
    normal = COSDictionary()
    for state in states:
        normal.set_item(COSName.get_pdf_name(state), COSDictionary())
    ap = COSDictionary()
    ap.set_item(_N, normal)
    return ap


def _widget_with_states(*states: str) -> PDAnnotationWidget:
    widget = PDAnnotationWidget()
    widget.get_cos_object().set_item(_AP, _normal_appearance(*states))
    return widget


def test_button_constructor_sets_field_type_for_new_field_only() -> None:
    form = PDAcroForm()

    fresh = PDButton(form)
    existing_dict = COSDictionary()
    existing = PDButton(form, existing_dict)

    assert fresh.get_cos_object().get_name(_FT) == "Btn"
    assert existing.get_cos_object() is existing_dict
    assert existing.get_cos_object().get_name(_FT) is None


def test_push_and_radio_flags_clear_each_other() -> None:
    button = PDButton(PDAcroForm())

    button.set_push_button(True)
    assert button.is_push_button()
    assert not button.is_radio_button()

    button.set_radio_button(True)
    assert button.is_radio_button()
    assert not button.is_push_button()

    button.set_push_button(False)
    button.set_radio_button(False)
    assert not button.is_push_button()
    assert not button.is_radio_button()


def test_string_values_and_defaults_can_be_detected_and_cleared() -> None:
    button = PDButton(PDAcroForm())
    button.get_cos_object().set_string(_V, "string-value")
    button.get_cos_object().set_string(_DV, "default-value")

    # The has_* helpers still detect a COSString token, but the value
    # readers mirror upstream PDButton.getValue / getDefaultValue: only an
    # ``instanceof COSName`` token is read. A COSString /V therefore reads
    # back as the default "Off" (getValue) / "" (getDefaultValue). Oracle:
    # PDFBox 3.0.7 returns "Off" and "" respectively for COSString tokens.
    assert button.has_value()
    assert button.get_value() == "Off"
    assert button.has_default_value()
    assert button.get_default_value() == ""

    button.clear_value()
    button.clear_default_value()

    assert not button.has_value()
    assert button.get_value() == "Off"
    assert not button.has_default_value()
    assert button.get_default_value() == ""


def test_export_values_accept_single_string_and_mixed_array_entries() -> None:
    button = PDButton(PDAcroForm())
    button.get_cos_object().set_item(_OPT, COSString("single"))

    assert button.has_export_values()
    assert button.get_export_values() == ["single"]

    values = COSArray()
    values.add(COSString("first"))
    values.add(COSName.get_pdf_name("Second"))
    values.add(COSDictionary())
    button.get_cos_object().set_item(_OPT, values)

    assert button.get_export_values() == ["first", "Second"]
    button.clear_export_values()
    assert not button.has_export_values()
    assert button.get_export_values() == []


def test_on_values_use_deduped_exports_before_widget_appearances() -> None:
    button = PDButton(PDAcroForm())
    button.set_export_values(["A", "A", "B"])
    button.set_widgets([_widget_with_states("WidgetOnly", "Off")])

    assert button.get_on_values() == {"A", "B"}


def test_on_values_include_empty_for_missing_or_off_only_widget_appearances() -> None:
    # Wave 1487: upstream PDButton.getOnValues adds getOnValueForWidget(widget)
    # for EVERY widget unconditionally, including the empty string "" for a
    # widget that lacks a usable /AP /N on-state. The set therefore holds
    # {"", "Yes"} (was {"Yes"} under the empty-skipping scaffold).
    button = PDButton(PDAcroForm())
    missing_ap = PDAnnotationWidget()
    missing_normal = PDAnnotationWidget()
    missing_normal.get_cos_object().set_item(_AP, COSDictionary())
    off_only = _widget_with_states("Off")
    valid = _widget_with_states("Yes", "Off")
    button.set_widgets([missing_ap, missing_normal, off_only, valid])

    on_values = button.get_on_values()
    assert on_values == {"", "Yes"}
    # Insertion order preserved (LinkedHashSet parity): "" first, then "Yes".
    assert list(on_values) == ["", "Yes"]


def test_construct_appearances_sets_matching_state_or_off() -> None:
    button = PDCheckBox(PDAcroForm())
    yes_widget = _widget_with_states("Yes", "Off")
    no_widget = _widget_with_states("No", "Off")
    malformed_widget = PDAnnotationWidget()
    malformed_widget.set_appearance_state("KeepMe")
    button.set_widgets([yes_widget, no_widget, malformed_widget])
    button.set_value("Yes")

    button.construct_appearances()

    assert yes_widget.get_appearance_state() == "Yes"
    assert no_widget.get_appearance_state() == "Off"
    assert malformed_widget.get_appearance_state() == "KeepMe"

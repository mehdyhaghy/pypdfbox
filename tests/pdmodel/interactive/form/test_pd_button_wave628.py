from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

_AP = COSName.get_pdf_name("AP")
_AS = COSName.get_pdf_name("AS")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_OPT = COSName.get_pdf_name("Opt")
_V = COSName.get_pdf_name("V")


def _widget_with_states(*states: str) -> PDAnnotationWidget:
    normal = COSDictionary()
    for state in states:
        normal.set_item(COSName.get_pdf_name(state), COSDictionary())
    ap = COSDictionary()
    ap.set_item(_N, normal)
    widget = PDAnnotationWidget()
    widget.get_cos_object().set_item(_AP, ap)
    return widget


def test_wave628_export_values_fall_back_to_acroform_inheritable_opt() -> None:
    form = PDAcroForm()
    form.get_cos_object().set_item(_OPT, COSString("inherited"))
    button = PDButton(form)

    assert button.has_export_values() is False
    assert button.get_export_values() == ["inherited"]
    assert button.get_on_values() == {"inherited"}

    button.set_export_values(["local"])
    assert button.has_export_values() is True
    assert button.get_export_values() == ["local"]

    button.clear_export_values()
    assert button.has_export_values() is False
    assert button.get_export_values() == ["inherited"]


def test_wave628_value_name_integer_outside_export_range_returns_raw_name() -> None:
    button = PDButton(PDAcroForm())
    button.set_export_values(["zero", "one"])

    button.get_cos_object().set_name(_V, "2")
    assert button.get_value() == "2"

    button.get_cos_object().set_name(_V, "-1")
    assert button.get_value() == "-1"


def test_wave628_set_value_by_index_rejects_empty_and_out_of_range_exports() -> None:
    button = PDButton(PDAcroForm())

    with pytest.raises(ValueError, match="valid indices are from 0 to -1"):
        button.set_value_by_index(0)

    button.set_export_values(["only"])
    with pytest.raises(ValueError, match="valid indices are from 0 to 0"):
        button.set_value_by_index(1)


def test_wave628_check_value_is_strict_even_when_sparse_set_value_is_permissive() -> None:
    button = PDButton(PDAcroForm())

    button.set_value("legacy")
    assert button.get_value() == "legacy"

    with pytest.raises(ValueError, match="not a valid option"):
        button.check_value("legacy")
    button.check_value("Off")


def test_wave628_default_value_uses_string_and_name_but_ignores_other_cos_types() -> None:
    button = PDButton(PDAcroForm())
    dv = COSName.get_pdf_name("DV")

    button.get_cos_object().set_string(dv, "string-default")
    assert button.has_default_value() is True
    assert button.get_default_value() == "string-default"

    button.get_cos_object().set_name(dv, "NameDefault")
    assert button.get_default_value() == "NameDefault"

    button.get_cos_object().set_item(dv, COSArray())
    assert button.has_default_value() is False
    assert button.get_default_value() == ""


def test_wave628_construct_appearances_uses_off_for_non_name_value() -> None:
    button = PDCheckBox(PDAcroForm())
    widget = _widget_with_states("Yes", "Off")
    button.set_widgets([widget])
    button.get_cos_object().set_string(_V, "Yes")

    button.construct_appearances()

    assert widget.get_cos_object().get_name(_AS) == "Off"


def test_wave628_on_value_for_widget_returns_empty_for_non_dictionary_normal_appearance() -> None:
    widget = PDAnnotationWidget()
    ap = COSDictionary()
    ap.set_item(_N, COSString("not-a-dictionary"))
    widget.get_cos_object().set_item(_AP, ap)

    assert PDButton.get_on_value_for_widget(widget) == ""

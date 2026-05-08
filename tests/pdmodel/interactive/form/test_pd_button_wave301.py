from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton

_AP: COSName = COSName.get_pdf_name("AP")
_KIDS: COSName = COSName.get_pdf_name("Kids")
_N: COSName = COSName.get_pdf_name("N")
_OFF: COSName = COSName.get_pdf_name("Off")


def _widget_with_on_state(on_value: str) -> COSDictionary:
    widget = COSDictionary()
    ap = COSDictionary()
    normal = COSDictionary()
    normal.set_item(COSName.get_pdf_name(on_value), COSDictionary())
    normal.set_item(_OFF, COSDictionary())
    ap.set_item(_N, normal)
    widget.set_item(_AP, ap)
    return widget


def test_wave301_button_set_value_rejects_unknown_when_on_states_known() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_AP, _widget_with_on_state("Yes").get_dictionary_object(_AP))

    cb.set_value("Yes")
    cb.set_value("Off")

    with pytest.raises(ValueError, match="not a valid option"):
        cb.set_value("Maybe")


def test_wave301_button_set_value_accepts_sparse_field_without_on_states() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)

    cb.set_value("LegacyValue")

    assert cb.get_value() == "LegacyValue"


def test_wave301_button_set_value_by_index_still_writes_index_name() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["one", "two"])

    rb.set_value_by_index(1)

    assert rb.get_cos_object().get_name(COSName.get_pdf_name("V")) == "1"
    assert rb.get_value() == "two"


def test_wave301_radio_set_value_rejects_unknown_widget_state() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    kids = COSArray()
    kids.add(_widget_with_on_state("A"))
    kids.add(_widget_with_on_state("B"))
    rb.get_cos_object().set_item(_KIDS, kids)

    rb.set_value("B")

    with pytest.raises(ValueError, match="not a valid option"):
        rb.set_value("C")

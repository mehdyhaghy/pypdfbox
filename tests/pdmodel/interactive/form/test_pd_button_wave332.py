from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_OFF: COSName = COSName.get_pdf_name("Off")


def _normal_appearance_with_on_state(on_value: str) -> COSDictionary:
    ap = COSDictionary()
    normal = COSDictionary()
    normal.set_item(COSName.get_pdf_name(on_value), COSDictionary())
    normal.set_item(_OFF, COSDictionary())
    ap.set_item(_N, normal)
    return ap


def test_wave332_button_set_default_value_rejects_unknown_known_state() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_AP, _normal_appearance_with_on_state("Yes"))

    cb.set_default_value("Yes")
    cb.set_default_value("Off")

    with pytest.raises(ValueError, match="not a valid option"):
        cb.set_default_value("Maybe")
    assert cb.get_default_value() == "Off"


def test_wave332_button_set_default_value_accepts_sparse_field() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)

    cb.set_default_value("LegacyDefault")

    assert cb.get_default_value() == "LegacyDefault"

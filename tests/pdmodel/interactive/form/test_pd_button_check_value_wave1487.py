"""Wave 1487 — PDButton strict checkValue + empty-string on-values.

Regression coverage for the divergence closed in wave 1487:

  * ``PDButton.get_on_values`` now includes the empty string ``""`` for every
    widget that lacks a usable ``/AP /N`` on-state (upstream adds
    ``getOnValueForWidget(widget)`` unconditionally), and preserves
    ``LinkedHashSet`` insertion order;
  * ``set_value`` / ``set_default_value`` route through the strict
    ``check_value`` (``IllegalArgumentException`` -> ``ValueError``), with no
    permissive fall-through for sparse/AP-less fields;
  * ``PDCheckBox.check`` sets the value to the discovered on-value (``""`` when
    none), not a ``"Yes"`` fallback, and ``is_checked`` is
    ``get_value() == get_on_value()``.

Behaviour pinned against the live oracle in
``oracle/test_button_check_value_oracle.py``; these are the hand-written API
exercises.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton

_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_V = COSName.get_pdf_name("V")
_KIDS = COSName.get_pdf_name("Kids")


def _normal_ap(on_state: str) -> COSDictionary:
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name(on_state), COSStream())
    n.set_item(_OFF, COSStream())
    ap = COSDictionary()
    ap.set_item(_N, n)
    return ap


def _widget_with_ap(on_state: str) -> COSDictionary:
    w = COSDictionary()
    w.set_item(_AP, _normal_ap(on_state))
    return w


# ---------- get_on_values: empty-string membership + order ----------


def test_get_on_values_includes_empty_for_ap_less_widgets() -> None:
    button = PDButton(PDAcroForm())
    kids = COSArray()
    kids.add(COSDictionary())  # no /AP -> ""
    kids.add(_widget_with_ap("Accepted"))
    kids.add(COSDictionary())  # no /AP -> "" (deduped)
    button.get_cos_object().set_item(_KIDS, kids)

    on_values = button.get_on_values()
    assert on_values == {"", "Accepted"}
    # LinkedHashSet insertion order: "" (kid 0) then "Accepted" (kid 1).
    assert list(on_values) == ["", "Accepted"]


def test_get_on_values_fresh_ap_less_button_is_single_empty() -> None:
    button = PDButton(PDAcroForm())
    on_values = button.get_on_values()
    assert on_values == {""}
    assert list(on_values) == [""]


def test_get_on_values_opt_dedups_and_preserves_order() -> None:
    rb = PDRadioButton(PDAcroForm())
    rb.set_export_values(["e1", "e2", "e1"])
    on_values = rb.get_on_values()
    assert on_values == {"e1", "e2"}
    assert list(on_values) == ["e1", "e2"]


# ---------- strict check_value / set_value ----------


def test_check_value_strict_rejects_unknown_name() -> None:
    cb = PDCheckBox(PDAcroForm())
    cb.get_cos_object().set_item(_AP, _normal_ap("Yes"))

    cb.check_value("Yes")
    cb.check_value("Off")
    with pytest.raises(ValueError, match="not a valid option"):
        cb.check_value("Maybe")


def test_check_value_accepts_empty_for_ap_less_button() -> None:
    cb = PDCheckBox(PDAcroForm())
    # on-values == {""} so "" and "Off" are valid; any other name is not.
    cb.check_value("")
    cb.check_value("Off")
    with pytest.raises(ValueError, match="not a valid option"):
        cb.check_value("Yes")


def test_set_value_routes_through_strict_check() -> None:
    cb = PDCheckBox(PDAcroForm())
    with pytest.raises(ValueError, match="not a valid option"):
        cb.set_value("Yes")
    # Accepted names land in /V.
    cb.set_value("Off")
    assert cb.get_value() == "Off"


def test_set_value_with_installed_ap_writes_cos_name() -> None:
    cb = PDCheckBox(PDAcroForm())
    cb.get_cos_object().set_item(_AP, _normal_ap("Yes"))
    cb.set_value("Yes")
    raw = cb.get_cos_object().get_dictionary_object(_V)
    assert isinstance(raw, COSName)
    assert raw.name == "Yes"
    assert cb.get_value() == "Yes"


def test_set_default_value_routes_through_strict_check() -> None:
    cb = PDCheckBox(PDAcroForm())
    cb.get_cos_object().set_item(_AP, _normal_ap("On"))
    cb.set_default_value("On")
    assert cb.get_default_value() == "On"
    with pytest.raises(ValueError, match="not a valid option"):
        cb.set_default_value("Bad")


def test_push_button_set_value_is_strict_empty_on_values() -> None:
    pb = PDPushButton(PDAcroForm())
    assert pb.get_on_values() == set()
    with pytest.raises(ValueError, match="not a valid option"):
        pb.set_value("anything")
    # "Off" is always accepted; the read side still reports "".
    pb.set_value("Off")
    assert pb.get_value() == ""


# ---------- PDCheckBox.check / is_checked ----------


def test_check_uses_discovered_on_value_not_yes_fallback() -> None:
    # Fresh AP-less box: get_on_value() is "" -> check() sets value "".
    cb = PDCheckBox(PDAcroForm())
    assert cb.get_on_value() == ""
    cb.check()
    assert cb.get_value() == ""
    assert cb.is_checked() is True
    cb.un_check()
    assert cb.get_value() == "Off"
    assert cb.is_checked() is False


def test_check_with_installed_ap_sets_on_state() -> None:
    cb = PDCheckBox(PDAcroForm())
    cb.get_cos_object().set_item(_AP, _normal_ap("Yes"))
    assert cb.get_on_value() == "Yes"
    cb.check()
    assert cb.get_value() == "Yes"
    assert cb.is_checked() is True

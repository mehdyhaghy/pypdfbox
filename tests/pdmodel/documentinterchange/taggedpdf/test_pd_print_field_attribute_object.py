from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDPrintFieldAttributeObject,
)


def test_defaults_when_absent() -> None:
    obj = PDPrintFieldAttributeObject()
    assert obj.get_owner() == "PrintField"
    assert obj.get_role() is None
    assert obj.get_checked() == "off"
    assert obj.get_checked() == PDPrintFieldAttributeObject.CHECKED_OFF
    assert obj.get_description() is None


def test_role_round_trip_all_values() -> None:
    for role in (
        PDPrintFieldAttributeObject.ROLE_RADIO_BUTTON,
        PDPrintFieldAttributeObject.ROLE_CHECK_BOX,
        PDPrintFieldAttributeObject.ROLE_PUSH_BUTTON,
        PDPrintFieldAttributeObject.ROLE_TEXT_VALUE,
    ):
        obj = PDPrintFieldAttributeObject()
        obj.set_role(role)
        assert obj.get_role() == role
        raw = obj.get_cos_object().get_dictionary_object("Role")
        assert isinstance(raw, COSName)
        assert raw.name == role


def test_checked_round_trip_all_values() -> None:
    for state in (
        PDPrintFieldAttributeObject.CHECKED_ON,
        PDPrintFieldAttributeObject.CHECKED_OFF,
        PDPrintFieldAttributeObject.CHECKED_NEUTRAL,
    ):
        obj = PDPrintFieldAttributeObject()
        obj.set_checked(state)
        assert obj.get_checked() == state
        raw = obj.get_cos_object().get_dictionary_object("checked")
        assert isinstance(raw, COSName)
        assert raw.name == state


def test_description_round_trip() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_description("Submit button")
    assert obj.get_description() == "Submit button"
    # PDFBox-style alias points to the same /Desc entry.
    assert obj.get_desc() == "Submit button"


def test_set_none_or_empty_removes_entry() -> None:
    obj = PDPrintFieldAttributeObject()
    obj.set_role(PDPrintFieldAttributeObject.ROLE_CHECK_BOX)
    obj.set_description("alt text")
    assert obj.get_cos_object().get_dictionary_object("Role") is not None
    assert obj.get_cos_object().get_dictionary_object("Desc") is not None

    obj.set_role(None)
    obj.set_description(None)
    assert obj.get_cos_object().get_dictionary_object("Role") is None
    assert obj.get_cos_object().get_dictionary_object("Desc") is None
    assert obj.get_role() is None
    assert obj.get_description() is None

    # Empty string also removes /Desc.
    obj.set_description("again")
    assert obj.get_cos_object().get_dictionary_object("Desc") is not None
    obj.set_description("")
    assert obj.get_cos_object().get_dictionary_object("Desc") is None
    assert obj.get_description() is None


def test_constants_resolve_to_expected_strings() -> None:
    assert PDPrintFieldAttributeObject.ROLE_RADIO_BUTTON == "rb"
    assert PDPrintFieldAttributeObject.ROLE_CHECK_BOX == "cb"
    assert PDPrintFieldAttributeObject.ROLE_PUSH_BUTTON == "pb"
    assert PDPrintFieldAttributeObject.ROLE_TEXT_VALUE == "tv"
    assert PDPrintFieldAttributeObject.CHECKED_ON == "on"
    assert PDPrintFieldAttributeObject.CHECKED_OFF == "off"
    assert PDPrintFieldAttributeObject.CHECKED_NEUTRAL == "neutral"

    obj = PDPrintFieldAttributeObject()
    obj.set_role(PDPrintFieldAttributeObject.ROLE_RADIO_BUTTON)
    obj.set_checked(PDPrintFieldAttributeObject.CHECKED_NEUTRAL)
    role_raw = obj.get_cos_object().get_dictionary_object("Role")
    checked_raw = obj.get_cos_object().get_dictionary_object("checked")
    assert isinstance(role_raw, COSName) and role_raw.name == "rb"
    assert isinstance(checked_raw, COSName) and checked_raw.name == "neutral"

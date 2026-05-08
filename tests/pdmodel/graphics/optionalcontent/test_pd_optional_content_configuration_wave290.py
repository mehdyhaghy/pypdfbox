from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentConfiguration,
    PDOptionalContentGroup,
)

_AS = COSName.get_pdf_name("AS")
_BASE_STATE = COSName.get_pdf_name("BaseState")
_CREATOR = COSName.get_pdf_name("Creator")
_LIST_MODE = COSName.get_pdf_name("ListMode")
_LOCKED = COSName.get_pdf_name("Locked")
_NAME = COSName.get_pdf_name("Name")
_ORDER = COSName.get_pdf_name("Order")
_RBGROUPS = COSName.get_pdf_name("RBGroups")


def test_scalar_presence_helpers_and_clears() -> None:
    cfg = PDOptionalContentConfiguration()

    assert not cfg.has_name()
    assert not cfg.has_creator()
    assert not cfg.has_base_state()

    cfg.set_name("Display")
    cfg.set_creator("pypdfbox")
    cfg.set_base_state("OFF")

    assert cfg.has_name()
    assert cfg.has_creator()
    assert cfg.has_base_state()

    cfg.clear_name()
    cfg.clear_creator()
    cfg.clear_base_state()

    assert cfg.get_name() is None
    assert cfg.get_creator() is None
    assert cfg.get_base_state() == "ON"
    assert cfg.get_cos_object().get_dictionary_object(_NAME) is None
    assert cfg.get_cos_object().get_dictionary_object(_CREATOR) is None
    assert cfg.get_cos_object().get_dictionary_object(_BASE_STATE) is None


def test_base_state_presence_ignores_malformed_raw_entry() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.get_cos_object().set_item(_BASE_STATE, COSDictionary())

    assert not cfg.has_base_state()
    assert cfg.get_base_state() == "ON"


def test_list_mode_has_clear_and_malformed_name_default() -> None:
    cfg = PDOptionalContentConfiguration()

    assert cfg.get_list_mode() == "AllPages"
    assert not cfg.has_list_mode()

    cfg.set_list_mode("VisiblePages")
    assert cfg.get_list_mode() == "VisiblePages"
    assert cfg.has_list_mode()

    cfg.clear_list_mode()
    assert cfg.get_list_mode() == "AllPages"
    assert not cfg.has_list_mode()
    assert cfg.get_cos_object().get_dictionary_object(_LIST_MODE) is None

    cfg.get_cos_object().set_item(_LIST_MODE, COSName.get_pdf_name("Bogus"))
    assert cfg.get_list_mode() == "AllPages"
    assert not cfg.has_list_mode()

    cfg.clear_list_mode()
    assert cfg.get_cos_object().get_dictionary_object(_LIST_MODE) is None


def test_array_presence_helpers_and_clears() -> None:
    cfg = PDOptionalContentConfiguration()
    group = PDOptionalContentGroup("Layer")

    order = COSArray()
    order.add(group.get_cos_object())
    cfg.set_order(order)
    assert cfg.has_order()
    cfg.clear_order()
    assert cfg.get_order() is None
    assert cfg.get_cos_object().get_dictionary_object(_ORDER) is None

    cfg.add_rbgroup([group])
    assert cfg.has_rbgroups()
    cfg.clear_rbgroups()
    assert cfg.get_rbgroups() == []
    assert cfg.get_cos_object().get_dictionary_object(_RBGROUPS) is None

    cfg.set_locked([group])
    assert cfg.has_locked()
    cfg.clear_locked()
    assert cfg.get_locked() == []
    assert cfg.get_cos_object().get_dictionary_object(_LOCKED) is None

    cfg.add_as_entry("View", ["View"], [group])
    assert cfg.has_as_array()
    cfg.clear_as_array()
    assert cfg.get_as_array() is None
    assert cfg.get_cos_object().get_dictionary_object(_AS) is None


def test_array_presence_helpers_ignore_malformed_raw_entries() -> None:
    cfg = PDOptionalContentConfiguration()

    cfg.get_cos_object().set_item(_ORDER, COSName.get_pdf_name("BadOrder"))
    cfg.get_cos_object().set_item(_RBGROUPS, COSName.get_pdf_name("BadGroups"))
    cfg.get_cos_object().set_item(_LOCKED, COSName.get_pdf_name("BadLocked"))
    cfg.get_cos_object().set_item(_AS, COSName.get_pdf_name("BadAS"))

    assert not cfg.has_order()
    assert not cfg.has_rbgroups()
    assert not cfg.has_locked()
    assert not cfg.has_as_array()

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_default_attribute_object import (
    PDDefaultAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf import PDLayoutAttributeObject

_A = COSName.get_pdf_name("A")
_O = COSName.get_pdf_name("O")
_R = COSName.get_pdf_name("R")
_LOGGER = "pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object"


def _owner_dictionary(owner: str | None) -> COSDictionary:
    dictionary = COSDictionary()
    if owner is not None:
        dictionary.set_name(_O, owner)
    return dictionary


def test_add_to_structure_element_adds_attribute_and_keeps_back_pointer_wave275() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(4)
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    attr.set_structure_element(elem)

    attr.add_to_structure_element()

    revs = elem.get_attributes()
    assert revs.size() == 1
    assert revs.get_object_at(0) is attr.get_cos_object()
    assert revs.get_revision_number_at(0) == 4
    assert attr.get_structure_element() is elem


def test_remove_from_structure_element_removes_attribute_and_clears_parent_wave275() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)

    attr.remove_from_structure_element()

    assert elem.get_attributes().is_empty()
    assert elem.get_cos_object().get_dictionary_object(_A) is None
    assert attr.get_structure_element() is None


def test_notify_change_updates_attribute_revision_to_parent_revision_wave275() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    elem.set_revision_number(9)

    attr.notify_change()

    assert elem.get_attributes().get_revision_number_at(0) == 9


@pytest.mark.parametrize(
    "method_name",
    [
        "add_to_structure_element",
        "remove_from_structure_element",
        "notify_change",
    ],
)
def test_parent_maintenance_without_back_pointer_is_noop_wave275(
    method_name: str, caplog: pytest.LogCaptureFixture
) -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    before = dict(attr.get_cos_object().entry_set())

    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        assert getattr(attr, method_name)() is None

    assert attr.get_structure_element() is None
    assert dict(attr.get_cos_object().entry_set()) == before
    assert any(method_name in record.message for record in caplog.records)


def test_owner_and_revision_presence_predicates_wave275() -> None:
    attr = PDAttributeObject()
    assert attr.get_owner() is None
    assert attr.has_owner() is False
    assert attr.get_revision_number() == 0
    assert attr.has_revision_number() is False

    attr.set_owner("Layout")
    attr.set_revision_number(0)

    assert attr.has_owner() is True
    assert attr.has_revision_number() is True


def test_revision_number_rejects_negative_values_wave275() -> None:
    attr = PDAttributeObject()
    attr.set_revision_number(2)

    with pytest.raises(ValueError, match="revision number"):
        attr.set_revision_number(-1)

    assert attr.get_revision_number() == 2
    assert attr.get_cos_object().get_int(_R) == 2


def test_factory_dispatches_known_owner_and_falls_back_for_unknown_wave275() -> None:
    layout = PDAttributeObject.create(_owner_dictionary("Layout"))
    unknown = PDAttributeObject.create(_owner_dictionary("Wave275Owner"))
    missing = PDAttributeObject.create(_owner_dictionary(None))

    assert isinstance(layout, PDLayoutAttributeObject)
    assert isinstance(unknown, PDDefaultAttributeObject)
    assert unknown.get_owner() == "Wave275Owner"
    assert isinstance(missing, PDDefaultAttributeObject)
    assert missing.get_owner() is None


def test_factory_rejects_non_dictionary_wave275() -> None:
    with pytest.raises(TypeError, match="COSDictionary"):
        PDAttributeObject.create(object())  # type: ignore[arg-type]


def test_string_helpers_wave275() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")

    assert str(attr) == "O=Layout"
    assert repr(attr) == "O=Layout"
    assert PDAttributeObject.array_to_string([]) == "[]"
    assert PDAttributeObject.array_to_string(["A", "B"]) == "[A, B]"
    assert PDAttributeObject.array_to_string((1.0, 2.5)) == "[1.0, 2.5]"


def test_array_to_string_rejects_none_wave275() -> None:
    with pytest.raises(TypeError, match="sequence"):
        PDAttributeObject.array_to_string(None)

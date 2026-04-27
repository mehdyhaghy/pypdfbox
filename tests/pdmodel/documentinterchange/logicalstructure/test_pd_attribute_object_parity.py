from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)

_R = COSName.get_pdf_name("R")


# ---------- /R revision number ----------


def test_get_revision_number_default_zero() -> None:
    attr = PDAttributeObject()
    assert attr.get_revision_number() == 0


def test_get_revision_number_default_zero_when_dict_has_only_owner() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    assert attr.get_revision_number() == 0


def test_set_revision_number_round_trip() -> None:
    attr = PDAttributeObject()
    attr.set_revision_number(3)
    assert attr.get_revision_number() == 3
    assert attr.get_cos_object().get_int(_R, -1) == 3


def test_set_revision_number_zero_round_trip() -> None:
    attr = PDAttributeObject()
    attr.set_revision_number(7)
    attr.set_revision_number(0)
    assert attr.get_revision_number() == 0


def test_set_revision_number_negative_rejected() -> None:
    attr = PDAttributeObject()
    with pytest.raises(ValueError):
        attr.set_revision_number(-1)


def test_get_revision_number_reads_existing_dict() -> None:
    cos = COSDictionary()
    cos.set_int(_R, 5)
    attr = PDAttributeObject(cos)
    assert attr.get_revision_number() == 5


# ---------- structure-element back-pointer ----------


def test_get_structure_element_default_none() -> None:
    attr = PDAttributeObject()
    assert attr.get_structure_element() is None


def test_set_structure_element_round_trip() -> None:
    attr = PDAttributeObject()
    elem = PDStructureElement(structure_type="P")
    attr.set_structure_element(elem)
    assert attr.get_structure_element() is elem


def test_set_structure_element_none_clears() -> None:
    attr = PDAttributeObject()
    elem = PDStructureElement(structure_type="P")
    attr.set_structure_element(elem)
    attr.set_structure_element(None)
    assert attr.get_structure_element() is None


# ---------- notify_change / add_to / remove_from stubs ----------


def test_notify_change_callable_and_no_op() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    snapshot = dict(attr.get_cos_object().entry_set())
    # Should not raise and should not mutate the underlying dictionary.
    assert attr.notify_change() is None
    assert dict(attr.get_cos_object().entry_set()) == snapshot


def test_notify_change_logs_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    attr = PDAttributeObject()
    with caplog.at_level(
        logging.DEBUG,
        logger=(
            "pypdfbox.pdmodel.documentinterchange.logicalstructure."
            "pd_attribute_object"
        ),
    ):
        attr.notify_change()
    assert any("notify_change" in rec.message for rec in caplog.records)


def test_add_to_structure_element_callable_no_op() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    assert attr.add_to_structure_element() is None
    # No mutation expected on the lite surface.
    assert attr.get_owner() == "Layout"


def test_remove_from_structure_element_callable_no_op() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    assert attr.remove_from_structure_element() is None
    assert attr.get_owner() == "Layout"


# ---------- delegating add_to / remove_from / notify_change ----------


def test_add_to_structure_element_delegates_to_owner() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    attr.set_structure_element(elem)
    attr.add_to_structure_element()
    revs = elem.get_attributes()
    assert revs.size() == 1
    # Identity round-trip: the attribute dict landed in /A.
    assert revs.get_object_at(0) is attr.get_cos_object()


def test_remove_from_structure_element_delegates_to_owner() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    assert elem.get_attributes().size() == 1
    attr.remove_from_structure_element()
    assert elem.get_attributes().size() == 0
    assert attr.get_structure_element() is None


def test_notify_change_delegates_to_owner_and_bumps_revision() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    elem.set_revision_number(9)
    attr.notify_change()
    assert elem.get_attributes().get_revision_number_at(0) == 9

"""Wave 1241 round-out: parity tests for the upstream change-notification
helpers on ``PDAttributeObject`` (``notify_changed`` / ``is_value_changed``
/ ``potentially_notify_changed`` / ``to_string``)."""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)

_LOGGER = (
    "pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object"
)
_O = COSName.get_pdf_name("O")


# ---------- is_value_changed ----------


def test_is_value_changed_both_none_returns_false_wave1241() -> None:
    assert PDAttributeObject.is_value_changed(None, None) is False


def test_is_value_changed_old_none_new_present_returns_true_wave1241() -> None:
    assert (
        PDAttributeObject.is_value_changed(None, COSInteger.get(7)) is True
    )


def test_is_value_changed_old_present_new_none_returns_true_wave1241() -> None:
    assert (
        PDAttributeObject.is_value_changed(COSInteger.get(7), None) is True
    )


def test_is_value_changed_equal_values_returns_false_wave1241() -> None:
    assert (
        PDAttributeObject.is_value_changed(
            COSInteger.get(8), COSInteger.get(8)
        )
        is False
    )


def test_is_value_changed_distinct_values_returns_true_wave1241() -> None:
    assert (
        PDAttributeObject.is_value_changed(
            COSInteger.get(1), COSInteger.get(2)
        )
        is True
    )


def test_is_value_changed_distinct_types_returns_true_wave1241() -> None:
    assert (
        PDAttributeObject.is_value_changed(
            COSInteger.get(1), COSString("1")
        )
        is True
    )


# ---------- potentially_notify_changed ----------


def test_potentially_notify_changed_no_op_when_unchanged_wave1241() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    elem.set_revision_number(5)

    # Equal values: no revision bump.
    attr.potentially_notify_changed(COSInteger.get(3), COSInteger.get(3))
    assert elem.get_attributes().get_revision_number_at(0) == 0


def test_potentially_notify_changed_fires_when_changed_wave1241() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    elem.set_revision_number(7)

    attr.potentially_notify_changed(COSInteger.get(3), COSInteger.get(4))
    assert elem.get_attributes().get_revision_number_at(0) == 7


def test_potentially_notify_changed_both_none_is_no_op_wave1241() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    # No back-pointer + both None should not raise nor mutate dict.
    snapshot = dict(attr.get_cos_object().entry_set())
    attr.potentially_notify_changed(None, None)
    assert dict(attr.get_cos_object().entry_set()) == snapshot


# ---------- notify_changed (upstream snake_case form) ----------


def test_notify_changed_no_back_pointer_logs_at_debug_wave1241(
    caplog: pytest.LogCaptureFixture,
) -> None:
    attr = PDAttributeObject()
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        attr.notify_changed()
    assert any("notify_changed" in rec.message for rec in caplog.records)


def test_notify_changed_delegates_to_structure_element_wave1241() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    elem.set_revision_number(11)

    attr.notify_changed()
    assert elem.get_attributes().get_revision_number_at(0) == 11


# ---------- to_string ----------


def test_to_string_matches_str_and_upstream_format_wave1241() -> None:
    attr = PDAttributeObject()
    attr.set_owner("Layout")

    assert attr.to_string() == "O=Layout"
    assert attr.to_string() == str(attr)


def test_to_string_with_no_owner_wave1241() -> None:
    attr = PDAttributeObject()
    assert attr.to_string() == "O=None"

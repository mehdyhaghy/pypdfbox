"""Tests for :class:`PDOptionalContentConfiguration` (pypdfbox-original
typed wrapper for the /D and /Configs entries — see
``pd_optional_content_configuration.py`` module docstring)."""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentConfiguration,
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def test_default_construction_is_empty() -> None:
    cfg = PDOptionalContentConfiguration()
    assert cfg.get_name() is None
    assert cfg.get_creator() is None
    assert cfg.get_base_state() == "ON"
    assert cfg.get_intent() == "View"
    assert cfg.get_intents() == []
    assert cfg.get_on() == []
    assert cfg.get_off() == []
    assert cfg.get_order() is None
    assert cfg.get_rbgroups() == []
    assert cfg.get_locked() == []
    assert cfg.get_as_array() is None


def test_name_and_creator_round_trip() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.set_name("Alt 1")
    cfg.set_creator("Acme Inc.")
    assert cfg.get_name() == "Alt 1"
    assert cfg.get_creator() == "Acme Inc."
    cfg.set_name(None)
    cfg.set_creator(None)
    assert cfg.get_name() is None
    assert cfg.get_creator() is None


def test_base_state_round_trip_and_validation() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.set_base_state("OFF")
    assert cfg.get_base_state() == "OFF"
    cfg.set_base_state("Unchanged")
    assert cfg.get_base_state() == "Unchanged"
    cfg.set_base_state("ON")
    assert cfg.get_base_state() == "ON"
    with pytest.raises(ValueError):
        cfg.set_base_state("Bogus")


def test_intent_string_and_array_forms() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.set_intent("Design")
    assert cfg.get_intent() == "Design"
    assert cfg.get_intents() == ["Design"]
    cfg.set_intent(["View", "Design"])
    assert cfg.get_intent() == ["View", "Design"]
    assert cfg.get_intents() == ["View", "Design"]
    cfg.set_intent(None)
    assert cfg.get_intent() == "View"  # spec default
    assert cfg.get_intents() == []
    with pytest.raises(TypeError):
        cfg.set_intent(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cfg.set_intent([1, 2])  # type: ignore[list-item]


def test_order_round_trip() -> None:
    cfg = PDOptionalContentConfiguration()
    g = PDOptionalContentGroup("L")
    arr = COSArray()
    arr.add(g.get_cos_object())
    cfg.set_order(arr)
    assert cfg.get_order() is arr
    cfg.set_order(None)
    assert cfg.get_order() is None
    with pytest.raises(TypeError):
        cfg.set_order("nope")  # type: ignore[arg-type]


def test_rbgroups_add_and_lookup() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    c = PDOptionalContentGroup("C")
    cfg.add_rbgroup([a, b])
    cfg.add_rbgroup([c])
    rbg = cfg.get_rbgroups()
    assert len(rbg) == 2
    assert [g.get_name() for g in rbg[0]] == ["A", "B"]
    assert [g.get_name() for g in rbg[1]] == ["C"]

    found = cfg.get_rbgroup_for(b)
    assert found is not None
    assert [g.get_name() for g in found] == ["A", "B"]
    assert cfg.get_rbgroup_for(PDOptionalContentGroup("Z")) is None

    with pytest.raises(TypeError):
        cfg.add_rbgroup(["not-an-ocg"])  # type: ignore[list-item]


def test_locked_round_trip_and_idempotent_add() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    cfg.set_locked([a, b])
    assert [g.get_name() for g in cfg.get_locked()] == ["A", "B"]
    assert cfg.is_locked(a) is True
    assert cfg.is_locked(PDOptionalContentGroup("C")) is False

    # Idempotent: adding A again does not duplicate.
    cfg.add_locked(a)
    assert len(cfg.get_locked()) == 2

    cfg.set_locked(None)
    assert cfg.get_locked() == []

    with pytest.raises(TypeError):
        cfg.set_locked(["bad"])  # type: ignore[list-item]


def test_add_as_entry_creates_usage_application_dict() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    entry = cfg.add_as_entry("View", ["View"], [a])
    as_arr = cfg.get_as_array()
    assert as_arr is not None
    assert as_arr.size() == 1
    event = entry.get_dictionary_object(COSName.get_pdf_name("Event"))
    assert event == COSName.get_pdf_name("View")
    cats = entry.get_dictionary_object(COSName.get_pdf_name("Category"))
    assert isinstance(cats, COSArray)
    assert cats.size() == 1


def test_properties_default_configuration_wrapper_shares_dict() -> None:
    props = PDOptionalContentProperties()
    cfg = props.get_default_configuration()
    assert cfg.get_cos_object() is props.get_cos_object().get_dictionary_object(
        COSName.D  # type: ignore[attr-defined]
    )
    cfg.set_creator("Test")
    # /D /Creator is now visible through the raw dict.
    d = props.get_cos_object().get_dictionary_object(COSName.D)  # type: ignore[attr-defined]
    assert isinstance(d, COSDictionary)
    assert d.get_string(COSName.get_pdf_name("Creator")) == "Test"


def test_properties_alt_configuration_lifecycle() -> None:
    props = PDOptionalContentProperties()
    assert props.get_configurations() == []
    cfg = PDOptionalContentConfiguration()
    cfg.set_name("Alt")
    returned = props.add_configuration(cfg)
    assert returned is cfg
    assert [c.get_name() for c in props.get_configurations()] == ["Alt"]
    assert props.get_configuration_names() == ["Alt"]
    assert props.get_configuration("Alt") is not None
    assert props.get_configuration("Missing") is None

    # Raw COSDictionary form.
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("Name"), "Raw")
    wrapped = props.add_configuration(raw)
    assert isinstance(wrapped, PDOptionalContentConfiguration)
    assert props.get_configuration_names() == ["Alt", "Raw"]

    with pytest.raises(TypeError):
        props.add_configuration("nope")  # type: ignore[arg-type]

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDUserAttributeObject,
)


def test_get_owner_properties_default_empty() -> None:
    obj = PDUserAttributeObject()
    assert obj.get_owner_properties() == []


def test_add_owner_property_round_trip() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("alpha", 42)
    obj.add_owner_property("beta", "hello", formatted="text", hidden=True)

    props = obj.get_owner_properties()
    assert len(props) == 2
    assert props[0] == {"N": "alpha", "V": 42, "F": None, "H": False}
    assert props[1] == {"N": "beta", "V": "hello", "F": "text", "H": True}


def test_set_owner_properties_replaces_existing_list() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("old", 1)
    obj.add_owner_property("stale", "drop-me", formatted="x", hidden=True)
    assert len(obj.get_owner_properties()) == 2

    obj.set_owner_properties(
        [
            {"N": "fresh", "V": True},
            {"N": "labelled", "V": 3.5, "F": "3.5", "H": False},
            {"N": "secret", "V": "hush", "H": True},
        ]
    )

    props = obj.get_owner_properties()
    assert len(props) == 3
    assert props[0] == {"N": "fresh", "V": True, "F": None, "H": False}
    assert props[1] == {"N": "labelled", "V": 3.5, "F": "3.5", "H": False}
    assert props[2] == {"N": "secret", "V": "hush", "F": None, "H": True}


def test_set_owner_properties_empty_clears() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("a", 1)
    obj.set_owner_properties([])
    assert obj.get_owner_properties() == []


def test_set_owner_properties_requires_name() -> None:
    obj = PDUserAttributeObject()
    import pytest

    with pytest.raises(ValueError):
        obj.set_owner_properties([{"V": 1}])


def test_remove_owner_property_returns_true_when_found() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("alpha", 1)
    obj.add_owner_property("beta", 2)
    obj.add_owner_property("gamma", 3)

    assert obj.remove_owner_property("beta") is True
    remaining = obj.get_owner_properties()
    assert [entry["N"] for entry in remaining] == ["alpha", "gamma"]


def test_remove_owner_property_returns_false_when_missing() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("alpha", 1)
    assert obj.remove_owner_property("does-not-exist") is False
    assert [entry["N"] for entry in obj.get_owner_properties()] == ["alpha"]


def test_remove_owner_property_no_p_array_returns_false() -> None:
    obj = PDUserAttributeObject()
    assert obj.remove_owner_property("anything") is False


def test_remove_owner_property_removes_only_first_match() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("dup", 1)
    obj.add_owner_property("dup", 2)
    obj.add_owner_property("dup", 3)

    assert obj.remove_owner_property("dup") is True
    remaining = obj.get_owner_properties()
    assert len(remaining) == 2
    assert [entry["V"] for entry in remaining] == [2, 3]


def test_hidden_flag_defaults_false_on_read() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("plain", "value")
    [entry] = obj.get_owner_properties()
    assert entry["H"] is False


def test_hidden_flag_omitted_when_false_on_write() -> None:
    # Round-trip: a property with hidden=False should not write /H, and
    # readers should still report H == False.
    obj = PDUserAttributeObject()
    obj.add_owner_property("plain", "value", hidden=False)

    p_array = obj._dictionary.get_dictionary_object("P")
    assert isinstance(p_array, COSArray)
    entry = p_array.get_object(0)
    assert isinstance(entry, COSDictionary)
    assert entry.get_dictionary_object("H") is None

    [props] = obj.get_owner_properties()
    assert props["H"] is False


def test_hidden_true_persists_as_cos_boolean() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("secret", "x", hidden=True)

    p_array = obj._dictionary.get_dictionary_object("P")
    assert isinstance(p_array, COSArray)
    entry = p_array.get_object(0)
    assert isinstance(entry, COSDictionary)
    assert entry.get_dictionary_object("H") is COSBoolean.TRUE


def test_get_property_alias_sees_owner_properties_writes() -> None:
    # The legacy get_property() and the new get_owner_properties() must
    # observe the same /P entries.
    obj = PDUserAttributeObject()
    obj.set_owner_properties([{"N": "x", "V": 1}])
    assert obj.get_property() == obj.get_owner_properties()

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSString,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDUserAttributeObject,
    PDUserProperty,
)

# ---------- construction ----------


def test_default_constructor_creates_empty_dictionary() -> None:
    prop = PDUserProperty()
    assert isinstance(prop.get_cos_object(), COSDictionary)
    assert prop.get_cos_object().size() == 0
    assert prop.get_name() is None
    assert prop.get_value() is None
    assert prop.get_formatted_value() is None
    assert prop.is_hidden() is False


def test_constructor_with_owner_only() -> None:
    owner = PDUserAttributeObject()
    prop = PDUserProperty(owner)
    assert prop.get_cos_object().size() == 0


def test_constructor_with_dictionary_wraps_existing_cos_name_n() -> None:
    # Upstream-convention storage: /N as COSName must still read back.
    dictionary = COSDictionary()
    dictionary.set_name("N", "color")
    dictionary.set_item("V", COSString("red"))
    owner = PDUserAttributeObject()
    prop = PDUserProperty(owner, dictionary)
    assert prop.get_cos_object() is dictionary
    assert prop.get_name() == "color"
    assert isinstance(prop.get_value(), COSString)
    assert prop.get_value().get_string() == "red"


def test_constructor_with_dictionary_wraps_existing_cos_string_n() -> None:
    # pypdfbox-convention storage: /N as COSString must also read back.
    dictionary = COSDictionary()
    dictionary.set_string("N", "color")
    dictionary.set_item("V", COSString("red"))
    prop = PDUserProperty(None, dictionary)
    assert prop.get_name() == "color"


# ---------- /N name ----------


def test_set_name_round_trip() -> None:
    prop = PDUserProperty()
    prop.set_name("alpha")
    assert prop.get_name() == "alpha"
    # Stored as COSString (pypdfbox convention; see CHANGES.md). Both
    # ``get_string`` and ``get_name`` ultimately tolerate the read in
    # pypdfbox, but the canonical storage type is COSString.
    assert prop.get_cos_object().get_string("N") == "alpha"


def test_set_name_overwrites() -> None:
    prop = PDUserProperty()
    prop.set_name("alpha")
    prop.set_name("beta")
    assert prop.get_name() == "beta"


# ---------- /V value ----------


def test_set_value_with_cos_string() -> None:
    prop = PDUserProperty()
    prop.set_value(COSString("hello"))
    value = prop.get_value()
    assert isinstance(value, COSString)
    assert value.get_string() == "hello"


def test_set_value_with_cos_integer() -> None:
    prop = PDUserProperty()
    prop.set_value(COSInteger.get(42))
    value = prop.get_value()
    assert isinstance(value, COSInteger)
    assert value.value == 42


def test_set_value_none_removes_entry() -> None:
    prop = PDUserProperty()
    prop.set_value(COSString("hi"))
    assert prop.get_value() is not None
    prop.set_value(None)
    assert prop.get_value() is None
    assert prop.get_cos_object().contains_key("V") is False


# ---------- /F formatted value ----------


def test_set_formatted_value_round_trip() -> None:
    prop = PDUserProperty()
    prop.set_formatted_value("3.14 m")
    assert prop.get_formatted_value() == "3.14 m"


def test_set_formatted_value_none_removes_entry() -> None:
    prop = PDUserProperty()
    prop.set_formatted_value("x")
    prop.set_formatted_value(None)
    assert prop.get_formatted_value() is None
    assert prop.get_cos_object().contains_key("F") is False


# ---------- /H hidden ----------


def test_is_hidden_default_false() -> None:
    prop = PDUserProperty()
    assert prop.is_hidden() is False


def test_set_hidden_true_persists_as_cos_boolean() -> None:
    prop = PDUserProperty()
    prop.set_hidden(True)
    raw = prop.get_cos_object().get_dictionary_object("H")
    assert raw is COSBoolean.TRUE
    assert prop.is_hidden() is True


def test_set_hidden_false_writes_explicit_false() -> None:
    # Upstream writes /H = false explicitly via setBoolean; we mirror that.
    prop = PDUserProperty()
    prop.set_hidden(False)
    raw = prop.get_cos_object().get_dictionary_object("H")
    assert raw is COSBoolean.FALSE
    assert prop.is_hidden() is False


# ---------- change notification ----------


def test_setter_notifies_owner_when_value_changes() -> None:
    calls: list[PDUserProperty] = []

    class Observer(PDUserAttributeObject):
        def user_property_changed(self, user_property: PDUserProperty) -> None:
            calls.append(user_property)

    owner = Observer()
    prop = PDUserProperty(owner)
    prop.set_name("alpha")
    prop.set_value(COSString("first"))
    prop.set_formatted_value("first")
    prop.set_hidden(True)
    assert len(calls) == 4
    assert all(c is prop for c in calls)


def test_setter_does_not_notify_when_value_unchanged() -> None:
    calls: list[PDUserProperty] = []

    class Observer(PDUserAttributeObject):
        def user_property_changed(self, user_property: PDUserProperty) -> None:
            calls.append(user_property)

    owner = Observer()
    prop = PDUserProperty(owner)
    prop.set_name("alpha")  # change: None -> "alpha"
    prop.set_name("alpha")  # no change
    assert len(calls) == 1


def test_setter_with_no_owner_does_not_raise() -> None:
    prop = PDUserProperty()  # no owner
    prop.set_name("alpha")
    prop.set_value(COSInteger.get(1))
    prop.set_formatted_value("x")
    prop.set_hidden(True)
    assert prop.get_name() == "alpha"


# ---------- repr / equality ----------


def test_repr_contains_all_fields() -> None:
    prop = PDUserProperty()
    prop.set_name("color")
    prop.set_value(COSString("red"))
    prop.set_formatted_value("Red")
    prop.set_hidden(True)
    text = repr(prop)
    assert "Name=color" in text
    assert "FormattedValue=Red" in text
    assert "Hidden=True" in text


def test_eq_identity() -> None:
    owner = PDUserAttributeObject()
    a = PDUserProperty(owner)
    assert a == a


def test_eq_distinct_dicts_differ() -> None:
    owner = PDUserAttributeObject()
    a = PDUserProperty(owner)
    a.set_name("alpha")
    b = PDUserProperty(owner)
    b.set_name("beta")
    assert a != b


def test_eq_same_dict_same_owner() -> None:
    owner = PDUserAttributeObject()
    dictionary = COSDictionary()
    dictionary.set_name("N", "alpha")
    a = PDUserProperty(owner, dictionary)
    b = PDUserProperty(owner, dictionary)
    assert a == b


def test_not_eq_other_type() -> None:
    prop = PDUserProperty()
    assert prop != "PDUserProperty"


# ---------- attribute-object integration ----------


def test_get_owner_user_properties_returns_typed_wrappers() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("alpha", 42)
    obj.add_owner_property("beta", "hello", formatted="text", hidden=True)

    props = obj.get_owner_user_properties()
    assert len(props) == 2
    assert all(isinstance(p, PDUserProperty) for p in props)
    assert props[0].get_name() == "alpha"
    first_value = props[0].get_value()
    assert isinstance(first_value, COSInteger)
    assert first_value.value == 42
    assert props[0].is_hidden() is False
    assert props[1].get_name() == "beta"
    assert props[1].get_formatted_value() == "text"
    assert props[1].is_hidden() is True


def test_set_user_properties_round_trip() -> None:
    obj = PDUserAttributeObject()

    p1 = PDUserProperty(obj)
    p1.set_name("alpha")
    p1.set_value(COSInteger.get(1))

    p2 = PDUserProperty(obj)
    p2.set_name("beta")
    p2.set_value(COSString("two"))
    p2.set_hidden(True)

    obj.set_user_properties([p1, p2])

    out = obj.get_owner_user_properties()
    assert len(out) == 2
    assert out[0].get_name() == "alpha"
    assert out[1].get_name() == "beta"
    assert out[1].is_hidden() is True


def test_add_user_property_appends() -> None:
    obj = PDUserAttributeObject()
    p = PDUserProperty(obj)
    p.set_name("solo")
    obj.add_user_property(p)
    out = obj.get_owner_user_properties()
    assert [w.get_name() for w in out] == ["solo"]


def test_add_user_property_creates_p_array_when_missing() -> None:
    obj = PDUserAttributeObject()
    # Confirm /P is absent before the first add.
    assert obj._dictionary.get_dictionary_object("P") is None
    p = PDUserProperty(obj)
    p.set_name("first")
    obj.add_user_property(p)
    assert obj._dictionary.get_dictionary_object("P") is not None


def test_remove_user_property_removes_entry() -> None:
    obj = PDUserAttributeObject()
    p1 = PDUserProperty(obj)
    p1.set_name("alpha")
    p2 = PDUserProperty(obj)
    p2.set_name("beta")
    obj.set_user_properties([p1, p2])

    obj.remove_user_property(p1)
    remaining = obj.get_owner_user_properties()
    assert [w.get_name() for w in remaining] == ["beta"]


def test_remove_user_property_none_is_noop() -> None:
    obj = PDUserAttributeObject()
    p = PDUserProperty(obj)
    p.set_name("alpha")
    obj.add_user_property(p)
    obj.remove_user_property(None)
    assert len(obj.get_owner_user_properties()) == 1


def test_remove_user_property_when_p_missing_is_noop() -> None:
    obj = PDUserAttributeObject()
    p = PDUserProperty(obj)
    p.set_name("alpha")
    # /P never created.
    obj.remove_user_property(p)  # must not raise
    assert obj.get_owner_user_properties() == []


# ---------- back-compat: dict surface still works ----------


def test_dict_surface_and_typed_surface_see_same_array() -> None:
    obj = PDUserAttributeObject()
    obj.add_owner_property("dict-side", 10, formatted="ten")

    typed = obj.get_owner_user_properties()
    assert len(typed) == 1
    assert typed[0].get_name() == "dict-side"
    assert typed[0].get_formatted_value() == "ten"

    # And the legacy dict accessor still returns dicts.
    legacy = obj.get_owner_properties()
    assert legacy == [{"N": "dict-side", "V": 10, "F": "ten", "H": False}]


def test_typed_setter_visible_to_dict_surface() -> None:
    obj = PDUserAttributeObject()
    p = PDUserProperty(obj)
    p.set_name("typed-side")
    p.set_value(COSString("v"))
    obj.add_user_property(p)

    legacy = obj.get_owner_properties()
    assert legacy == [{"N": "typed-side", "V": "v", "F": None, "H": False}]


# ---------- guard: setter rejects unsupported type via dict surface ----------


def test_dict_surface_rejects_unsupported_value_type() -> None:
    obj = PDUserAttributeObject()
    with pytest.raises(TypeError):
        obj.add_owner_property("oops", object())

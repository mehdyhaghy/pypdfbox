"""Upstream parity tests for ``PDUserProperty``.

Apache PDFBox 3.0.x ships no ``PDUserPropertyTest`` — the class is
exercised indirectly through structure-tree integration tests. This file
mirrors the public/protected method surface of
``org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDUserProperty``
(see ``/tmp/pdfbox/.../PDUserProperty.java``) so future upstream re-syncs
have a parity scaffold already in place.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDUserAttributeObject,
    PDUserProperty,
)

# ---------- constructors ----------


def test_constructor_with_owner_only_creates_empty_cos_dictionary() -> None:
    # Mirrors ``PDUserProperty(PDUserAttributeObject)`` (Java L39-L42).
    owner = PDUserAttributeObject()
    prop = PDUserProperty(owner)
    cos = prop.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_constructor_with_dictionary_and_owner_wraps_dictionary() -> None:
    # Mirrors ``PDUserProperty(COSDictionary, PDUserAttributeObject)``
    # (Java L50-L55).
    dictionary = COSDictionary()
    dictionary.set_name("N", "color")
    owner = PDUserAttributeObject()
    prop = PDUserProperty(owner, dictionary)
    assert prop.get_cos_object() is dictionary
    assert prop.get_name() == "color"


# ---------- get_name / set_name (Java L63-L77) ----------


def test_get_name_returns_none_when_unset() -> None:
    prop = PDUserProperty()
    assert prop.get_name() is None


def test_set_name_round_trip() -> None:
    prop = PDUserProperty()
    prop.set_name("color")
    assert prop.get_name() == "color"


# ---------- get_value / set_value (Java L84-L98) ----------


def test_get_value_returns_none_when_unset() -> None:
    prop = PDUserProperty()
    assert prop.get_value() is None


def test_set_value_round_trip() -> None:
    prop = PDUserProperty()
    prop.set_value(COSString("red"))
    value = prop.get_value()
    assert isinstance(value, COSString)
    assert value.get_string() == "red"


# ---------- get_formatted_value / set_formatted_value (Java L105-L119) ----------


def test_set_formatted_value_round_trip() -> None:
    prop = PDUserProperty()
    prop.set_formatted_value("Red")
    assert prop.get_formatted_value() == "Red"


# ---------- is_hidden / set_hidden (Java L127-L142) ----------


def test_is_hidden_default_false() -> None:
    prop = PDUserProperty()
    assert prop.is_hidden() is False


def test_set_hidden_round_trip() -> None:
    prop = PDUserProperty()
    prop.set_hidden(True)
    assert prop.is_hidden() is True


# ---------- to_string (Java L146-L152) ----------


def test_to_string_format() -> None:
    prop = PDUserProperty()
    prop.set_name("color")
    prop.set_value(COSString("red"))
    prop.set_formatted_value("Red")
    prop.set_hidden(True)
    text = prop.to_string()
    assert "Name=color" in text
    assert "FormattedValue=Red" in text
    assert "Hidden=True" in text


def test_to_string_matches_repr() -> None:
    prop = PDUserProperty()
    prop.set_name("alpha")
    assert prop.to_string() == repr(prop)


# ---------- potentially_notify_changed (Java L161-L167) ----------


def test_potentially_notify_changed_no_op_when_unchanged() -> None:
    calls: list[PDUserProperty] = []

    class Observer(PDUserAttributeObject):
        def user_property_changed(self, user_property: PDUserProperty) -> None:
            calls.append(user_property)

    owner = Observer()
    prop = PDUserProperty(owner)
    prop.potentially_notify_changed("alpha", "alpha")
    assert calls == []


def test_potentially_notify_changed_fires_when_changed() -> None:
    calls: list[PDUserProperty] = []

    class Observer(PDUserAttributeObject):
        def user_property_changed(self, user_property: PDUserProperty) -> None:
            calls.append(user_property)

    owner = Observer()
    prop = PDUserProperty(owner)
    prop.potentially_notify_changed(None, "alpha")
    assert calls == [prop]


def test_potentially_notify_changed_with_no_owner_is_no_op() -> None:
    prop = PDUserProperty()  # no owner
    # Must not raise even though there is no attribute object to notify.
    prop.potentially_notify_changed(None, "alpha")


# ---------- is_entry_changed (Java L177-L184) ----------


def test_is_entry_changed_old_none_new_none_returns_false() -> None:
    assert PDUserProperty.is_entry_changed(None, None) is False


def test_is_entry_changed_old_none_new_set_returns_true() -> None:
    assert PDUserProperty.is_entry_changed(None, "alpha") is True


def test_is_entry_changed_equal_values_returns_false() -> None:
    assert PDUserProperty.is_entry_changed("alpha", "alpha") is False


def test_is_entry_changed_distinct_values_returns_true() -> None:
    assert PDUserProperty.is_entry_changed("alpha", "beta") is True


# ---------- equals / hash_code (Java L186-L224) ----------


def test_equals_self_returns_true() -> None:
    owner = PDUserAttributeObject()
    prop = PDUserProperty(owner)
    assert prop.equals(prop) is True


def test_equals_different_type_returns_false() -> None:
    prop = PDUserProperty()
    assert prop.equals("not a user property") is False


def test_equals_same_dict_same_owner_returns_true() -> None:
    dictionary = COSDictionary()
    dictionary.set_string("N", "color")
    owner = PDUserAttributeObject()
    a = PDUserProperty(owner, dictionary)
    b = PDUserProperty(owner, dictionary)
    assert a.equals(b) is True


def test_equals_different_dicts_returns_false() -> None:
    owner = PDUserAttributeObject()
    a = PDUserProperty(owner)
    a.set_name("alpha")
    b = PDUserProperty(owner)
    b.set_name("beta")
    assert a.equals(b) is False


def test_hash_code_returns_int() -> None:
    prop = PDUserProperty()
    prop.set_name("color")
    result = prop.hash_code()
    assert isinstance(result, int)


def test_hash_code_combines_owner() -> None:
    # Different owners => different hash_code values (id-based combine).
    owner_a = PDUserAttributeObject()
    owner_b = PDUserAttributeObject()
    dictionary = COSDictionary()
    a = PDUserProperty(owner_a, dictionary)
    b = PDUserProperty(owner_b, dictionary)
    assert a.hash_code() != b.hash_code()


# ---------- get_cos_object (Java inherits from PDDictionaryWrapper) ----------


def test_get_cos_object_returns_underlying_dictionary() -> None:
    dictionary = COSDictionary()
    prop = PDUserProperty(None, dictionary)
    assert prop.get_cos_object() is dictionary


# ---------- value-type fan-out (parity smoke) ----------


def test_set_value_with_cos_integer_round_trip() -> None:
    prop = PDUserProperty()
    prop.set_value(COSInteger.get(7))
    value = prop.get_value()
    assert isinstance(value, COSInteger)
    assert value.value == 7

"""
Hand-written parity tests for the upstream-named entry points added to
:class:`pypdfbox.xmpbox.XMPSchema` (cluster #1 surface fill-out). These cover
the aliases that mirror ``org.apache.xmpbox.schema.XMPSchema`` so that callers
porting Java code recognize the API verbatim — see CLAUDE.md (Hard Rules /
Compatibility preservation).
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata, XMPSchema


def _schema() -> XMPSchema:
    return XMPSchema(
        XMPMetadata.create_xmp_metadata(),
        namespace_uri="http://example.com/ns#",
        prefix="ex",
    )


# --- text property aliases ---------------------------------------------------


def test_add_unqualified_text_property_round_trip() -> None:
    s = _schema()
    s.add_unqualified_text_property("Title", "hello")
    assert s.get_unqualified_text_property("Title") == "hello"
    # alias path matches the older typed accessor
    assert s.get_unqualified_text_property_value("Title") == "hello"
    assert s.get_unqualified_text_property("Missing") is None


def test_set_text_property_value_alias_to_add() -> None:
    s = _schema()
    s.set_text_property_value("Producer", "p1")
    assert s.get_unqualified_text_property("Producer") == "p1"
    # add_unqualified_text_property has cardinality 1: it replaces.
    s.add_unqualified_text_property("Producer", "p2")
    assert s.get_unqualified_text_property("Producer") == "p2"


# --- bag / array helpers -----------------------------------------------------


def test_add_unqualified_bag_value_and_get_unqualified_array_list() -> None:
    s = _schema()
    s.add_unqualified_bag_value("subject", "alpha")
    s.add_unqualified_bag_value("subject", "beta")
    assert s.get_unqualified_array_list("subject") == ["alpha", "beta"]
    # Confirm the array view is a copy — mutating it must not corrupt storage.
    snapshot = s.get_unqualified_array_list("subject")
    assert snapshot is not None
    snapshot.append("gamma")
    assert s.get_unqualified_array_list("subject") == ["alpha", "beta"]


def test_get_unqualified_array_list_returns_none_when_missing() -> None:
    s = _schema()
    assert s.get_unqualified_array_list("nope") is None


def test_add_unqualified_array_installs_empty_list() -> None:
    s = _schema()
    items = s.add_unqualified_array("creators", XMPSchema.ORDERED_ARRAY)
    assert items == []
    assert s.get_unqualified_array_list("creators") == []
    # Subsequent appends via the canonical seq helper go into the same store.
    s.add_unqualified_sequence_value("creators", "Z")
    assert s.get_unqualified_array_list("creators") == ["Z"]


def test_add_unqualified_array_rejects_unknown_type() -> None:
    s = _schema()
    with pytest.raises(ValueError):
        s.add_unqualified_array("foo", "Tuple")


def test_remove_unqualified_bag_value_removes_all_matches() -> None:
    s = _schema()
    s.add_unqualified_bag_value("subject", "alpha")
    s.add_unqualified_bag_value("subject", "beta")
    s.add_unqualified_bag_value("subject", "alpha")

    s.remove_unqualified_bag_value("subject", "alpha")

    assert s.get_unqualified_bag_value_list("subject") == ["beta"]


def test_remove_unqualified_sequence_value_removes_all_matches() -> None:
    s = _schema()
    s.add_unqualified_sequence_value("creators", "Alice")
    s.add_unqualified_sequence_value("creators", "Bob")
    s.add_unqualified_sequence_value("creators", "Alice")

    s.remove_unqualified_sequence_value("creators", "Alice")

    assert s.get_unqualified_sequence_value_list("creators") == ["Bob"]


def test_remove_unqualified_language_property_value() -> None:
    s = _schema()
    s.set_unqualified_language_property_value("title", None, "Default")
    s.set_unqualified_language_property_value("title", "en-US", "English")

    s.remove_unqualified_language_property_value("title", None)

    assert s.get_unqualified_language_property_value("title", None) is None
    assert s.get_unqualified_language_property_value("title", "en-US") == "English"
    assert s.get_unqualified_language_property_languages_value("title") == ["en-US"]


# --- about attribute round-trip ---------------------------------------------


def test_get_about_attribute_round_trip() -> None:
    s = _schema()
    # Empty until set — upstream returns null for unset rdf:about.
    assert s.get_about_attribute() is None
    assert s.get_about_value() is None
    s.set_about("urn:foo")
    assert s.get_about_attribute() == "urn:foo"
    assert s.get_about_value() == "urn:foo"
    # set_about_as_simple is the upstream alias and shares storage.
    s.set_about_as_simple("urn:bar")
    assert s.get_about_attribute() == "urn:bar"
    assert s.get_about() == "urn:bar"


# --- generic property API ---------------------------------------------------


def test_get_unqualified_property_returns_raw_value() -> None:
    s = _schema()
    s.set_text_property_value("Title", "t")
    assert s.get_unqualified_property("Title") == "t"
    assert s.get_unqualified_property("Missing") is None


def test_add_property_accepts_tuple_and_duck_typed_field() -> None:
    s = _schema()
    s.add_property(("k1", "v1"))
    assert s.get_unqualified_text_property("k1") == "v1"

    class _Field:
        def get_property_name(self) -> str:
            return "k2"

        def get_value(self) -> str:
            return "v2"

    s.add_property(_Field())
    assert s.get_unqualified_text_property("k2") == "v2"


def test_add_property_rejects_other_shapes() -> None:
    s = _schema()
    with pytest.raises(TypeError):
        s.add_property(object())


def test_remove_property_clears_storage() -> None:
    s = _schema()
    s.set_text_property_value("k", "v")
    assert s.get_unqualified_text_property("k") == "v"
    s.remove_property("k")
    assert s.get_unqualified_text_property("k") is None
    # Removing a missing property is a no-op.
    s.remove_property("k")


# --- LangAlt ordering --------------------------------------------------------


def test_lang_alt_default_language_is_reorganized_first() -> None:
    s = _schema()
    s.set_unqualified_language_property_value("title", "fr-FR", "Bonjour")
    s.set_unqualified_language_property_value("title", None, "Hello")
    s.set_unqualified_language_property_value("title", "de-DE", "Hallo")

    assert s.get_unqualified_language_property_languages_value("title") == [
        "x-default",
        "fr-FR",
        "de-DE",
    ]
    assert s.get_unqualified_language_property_value("title") == "Hello"
    assert s.get_unqualified_language_property_value("title", "fr-FR") == "Bonjour"


def test_lang_alt_default_update_keeps_existing_language_order() -> None:
    s = _schema()
    s.set_unqualified_language_property_value("title", "fr-FR", "Bonjour")
    s.set_unqualified_language_property_value("title", None, "Hello")
    s.set_unqualified_language_property_value("title", "de-DE", "Hallo")
    s.set_unqualified_language_property_value("title", None, "Updated")

    assert s.get_unqualified_language_property_languages_value("title") == [
        "x-default",
        "fr-FR",
        "de-DE",
    ]
    assert s.get_unqualified_language_property_value("title") == "Updated"


# --- get_abstract_property --------------------------------------------------


def test_get_abstract_property_returns_value_or_none() -> None:
    s = _schema()
    s.set_text_property_value("Title", "hello")
    assert s.get_abstract_property("Title") == "hello"
    assert s.get_abstract_property("Missing") is None


# --- set_text_property_value null-clear semantics ---------------------------


def test_set_text_property_value_none_clears_property() -> None:
    s = _schema()
    s.set_text_property_value("Title", "hello")
    assert s.get_unqualified_text_property("Title") == "hello"
    s.set_text_property_value("Title", None)
    assert s.get_unqualified_text_property("Title") is None
    # Clearing a missing property is a no-op.
    s.set_text_property_value("Missing", None)
    assert s.get_unqualified_text_property("Missing") is None


def test_set_text_property_value_as_simple_none_clears_property() -> None:
    s = _schema()
    s.set_text_property_value_as_simple("Title", "hello")
    s.set_text_property_value_as_simple("Title", None)
    assert s.get_unqualified_text_property("Title") is None


# --- add_bag_value_as_simple ------------------------------------------------


def test_add_bag_value_as_simple_appends() -> None:
    s = _schema()
    s.add_bag_value_as_simple("subject", "alpha")
    s.add_bag_value_as_simple("subject", "beta")
    assert s.get_unqualified_bag_value_list("subject") == ["alpha", "beta"]


# --- Boolean property accessors ---------------------------------------------


def test_set_and_get_boolean_property_value_round_trip() -> None:
    s = _schema()
    s.set_boolean_property_value("Marked", True)
    assert s.get_boolean_property_value("Marked") is True
    s.set_boolean_property_value("Marked", False)
    assert s.get_boolean_property_value("Marked") is False
    assert s.get_boolean_property_value("Missing") is None


def test_set_boolean_property_value_none_clears() -> None:
    s = _schema()
    s.set_boolean_property_value("Marked", True)
    s.set_boolean_property_value("Marked", None)
    assert s.get_boolean_property_value("Marked") is None


def test_boolean_property_value_as_simple_aliases() -> None:
    s = _schema()
    s.set_boolean_property_value_as_simple("Marked", True)
    assert s.get_boolean_property_value_as_simple("Marked") is True


def test_get_boolean_property_value_returns_none_for_non_bool_storage() -> None:
    s = _schema()
    s.set_text_property_value("Title", "hello")
    # Stored value is a str — boolean accessor must not coerce it.
    assert s.get_boolean_property_value("Title") is None


# --- Integer property accessors ---------------------------------------------


def test_set_and_get_integer_property_value_round_trip() -> None:
    s = _schema()
    s.set_integer_property_value("Count", 42)
    assert s.get_integer_property_value("Count") == 42
    s.set_integer_property_value("Count", 0)
    assert s.get_integer_property_value("Count") == 0
    assert s.get_integer_property_value("Missing") is None


def test_set_integer_property_value_none_clears() -> None:
    s = _schema()
    s.set_integer_property_value("Count", 7)
    s.set_integer_property_value("Count", None)
    assert s.get_integer_property_value("Count") is None


def test_integer_property_value_as_simple_aliases() -> None:
    s = _schema()
    s.set_integer_property_value_as_simple("Count", 5)
    assert s.get_integer_property_value_as_simple("Count") == 5


def test_set_integer_property_value_rejects_bool() -> None:
    s = _schema()
    with pytest.raises(TypeError):
        s.set_integer_property_value("Count", True)


def test_get_integer_property_value_excludes_bool_storage() -> None:
    s = _schema()
    # Booleans are int-subclass in Python; the integer accessor must not
    # surface a stored bool.
    s.set_boolean_property_value("Marked", True)
    assert s.get_integer_property_value("Marked") is None


def test_get_integer_property_value_returns_none_for_non_int_storage() -> None:
    s = _schema()
    s.set_text_property_value("Title", "hello")
    assert s.get_integer_property_value("Title") is None

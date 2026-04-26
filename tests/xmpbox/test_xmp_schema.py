from __future__ import annotations

from pypdfbox.xmpbox import XMPMetadata, XMPSchema


def _schema() -> XMPSchema:
    return XMPSchema(
        XMPMetadata.create_xmp_metadata(),
        namespace_uri="http://example.com/ns#",
        prefix="ex",
    )


def test_text_property_round_trip() -> None:
    s = _schema()
    s.set_text_property_value("Title", "hello")
    assert s.get_property("Title") == "hello"
    assert s.get_unqualified_text_property_value("Title") == "hello"
    assert s.get_unqualified_text_property_value("Missing") is None


def test_bag_add_remove_and_list() -> None:
    s = _schema()
    s.add_qualified_bag_value("subject", "alpha")
    s.add_qualified_bag_value("subject", "beta")
    assert s.get_unqualified_bag_value_list("subject") == ["alpha", "beta"]
    s.remove_unqualified_bag_value("subject", "alpha")
    assert s.get_unqualified_bag_value_list("subject") == ["beta"]
    # Removing a missing value is a no-op (matches upstream).
    s.remove_unqualified_bag_value("subject", "nope")
    assert s.get_unqualified_bag_value_list("subject") == ["beta"]


def test_sequence_preserves_order() -> None:
    s = _schema()
    s.add_unqualified_sequence_value("creator", "Z")
    s.add_unqualified_sequence_value("creator", "A")
    assert s.get_unqualified_sequence_value_list("creator") == ["Z", "A"]


def test_lang_alt_default_and_explicit() -> None:
    s = _schema()
    s.set_unqualified_language_property_value("title", None, "Default")
    s.set_unqualified_language_property_value("title", "fr", "Bonjour")
    assert s.get_unqualified_language_property_value("title") == "Default"
    assert s.get_unqualified_language_property_value("title", "fr") == "Bonjour"
    assert s.get_unqualified_language_property_value("title", "de") is None
    langs = s.get_unqualified_language_property_languages_value("title") or []
    assert set(langs) == {"x-default", "fr"}


def test_about_round_trip() -> None:
    s = _schema()
    assert s.get_about() == ""
    s.set_about_as_simple("urn:foo")
    assert s.get_about() == "urn:foo"
    s.set_about("urn:bar")
    assert s.get_about() == "urn:bar"


def test_namespace_registry_includes_self() -> None:
    s = _schema()
    assert s.get_namespaces() == {"ex": "http://example.com/ns#"}
    s.add_namespace("foo", "http://foo/")
    assert s.get_namespaces()["foo"] == "http://foo/"

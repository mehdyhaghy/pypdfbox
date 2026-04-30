from __future__ import annotations

import pytest

from pypdfbox.xmpbox import Attribute, Cardinality, LangAlt, TextType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_lang_alt_is_alt_array(metadata: XMPMetadata) -> None:
    la = LangAlt(metadata, "ns", "p", "title")
    assert la.get_array_type() is Cardinality.Alt
    assert la.get_property_name() == "title"


def test_lang_alt_set_get_round_trip(metadata: XMPMetadata) -> None:
    la = LangAlt(metadata, "ns", "p", "title")
    la.set_language_value(None, "default")
    la.set_language_value("en-US", "english")
    la.set_language_value("fr-FR", "francais")
    assert la.get_language_value(None) == "default"
    assert la.get_language_value("en-US") == "english"
    assert la.get_language_value("fr-FR") == "francais"


def test_lang_alt_x_default_first(metadata: XMPMetadata) -> None:
    la = LangAlt(metadata, "ns", "p", "title")
    la.set_language_value("en-US", "english")
    la.set_language_value("fr-FR", "francais")
    la.set_language_value(None, "default")
    children = la.get_all_properties()
    first_attr = children[0].get_attribute("xml:lang")
    assert first_attr is not None
    assert first_attr.get_value() == "x-default"


def test_lang_alt_overwrites_same_language(metadata: XMPMetadata) -> None:
    la = LangAlt(metadata, "ns", "p", "title")
    la.set_language_value("en-US", "first")
    la.set_language_value("en-US", "second")
    assert la.get_language_value("en-US") == "second"
    assert len(la.get_all_properties()) == 1


def test_lang_alt_overwrite_removes_duplicate_existing_language(
    metadata: XMPMetadata,
) -> None:
    la = LangAlt(metadata, "ns", "p", "title")
    for value in ("first", "second"):
        child = TextType(metadata, "ns", "p", "title", value)
        child.set_attribute(
            Attribute("http://www.w3.org/XML/1998/namespace", "xml:lang", "en-US")
        )
        la.add_property(child)

    la.set_language_value("en-US", "third")

    assert la.get_language_value("en-US") == "third"
    assert len(la.get_all_properties()) == 1


def test_lang_alt_languages_list(metadata: XMPMetadata) -> None:
    la = LangAlt(metadata, "ns", "p", "title")
    la.set_language_value("en-US", "a")
    la.set_language_value("de-DE", "b")
    languages = la.get_languages()
    assert "en-US" in languages
    assert "de-DE" in languages


def test_lang_alt_remove_language(metadata: XMPMetadata) -> None:
    la = LangAlt(metadata, "ns", "p", "title")
    la.set_language_value("en-US", "a")
    la.set_language_value("de-DE", "b")
    la.remove_language("en-US")
    assert la.get_language_value("en-US") is None
    assert la.get_language_value("de-DE") == "b"


def test_lang_alt_children_carry_xml_lang(metadata: XMPMetadata) -> None:
    la = LangAlt(metadata, "ns", "p", "title")
    la.set_language_value("en-US", "english")
    child = la.get_all_properties()[0]
    assert isinstance(child, TextType)
    attr = child.get_attribute("xml:lang")
    assert attr is not None
    assert attr.get_namespace() == "http://www.w3.org/XML/1998/namespace"
    assert attr.get_value() == "en-US"

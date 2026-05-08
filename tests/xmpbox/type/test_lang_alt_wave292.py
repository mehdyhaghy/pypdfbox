from __future__ import annotations

import pytest

from pypdfbox.xmpbox import Attribute, IntegerType, LangAlt, TextType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def _set_xml_lang(child: TextType | IntegerType, language: str) -> None:
    child.set_attribute(
        Attribute("http://www.w3.org/XML/1998/namespace", "xml:lang", language)
    )


def test_lang_alt_languages_ignore_malformed_non_text_children(
    metadata: XMPMetadata,
) -> None:
    lang_alt = LangAlt(metadata, "ns", "p", "title")
    malformed = IntegerType(metadata, "ns", "p", "title", 1)
    _set_xml_lang(malformed, "en-US")
    lang_alt.add_property(malformed)
    lang_alt.set_language_value("fr-FR", "bonjour")

    assert lang_alt.get_language_value("en-US") is None
    assert lang_alt.get_languages() == ["fr-FR"]


def test_lang_alt_remove_language_skips_malformed_non_text_children(
    metadata: XMPMetadata,
) -> None:
    lang_alt = LangAlt(metadata, "ns", "p", "title")
    malformed = IntegerType(metadata, "ns", "p", "title", 1)
    _set_xml_lang(malformed, "en-US")
    lang_alt.add_property(malformed)
    lang_alt.set_language_value("en-US", "hello")

    lang_alt.remove_language("en-US")

    assert lang_alt.get_language_value("en-US") is None
    assert malformed in lang_alt.get_all_properties()


def test_lang_alt_x_default_order_ignores_malformed_non_text_children(
    metadata: XMPMetadata,
) -> None:
    lang_alt = LangAlt(metadata, "ns", "p", "title")
    malformed = IntegerType(metadata, "ns", "p", "title", 1)
    _set_xml_lang(malformed, "x-default")
    lang_alt.add_property(malformed)
    lang_alt.set_language_value("en-US", "hello")
    lang_alt.set_language_value(None, "default")

    children = lang_alt.get_all_properties()
    assert isinstance(children[0], TextType)
    attr = children[0].get_attribute("xml:lang")
    assert attr is not None
    assert attr.get_value() == "x-default"
    assert malformed in children

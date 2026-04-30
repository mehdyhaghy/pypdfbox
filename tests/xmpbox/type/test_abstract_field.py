from __future__ import annotations

import pytest

from pypdfbox.xmpbox import Attribute, TextType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_attribute_construction_and_accessors() -> None:
    attr = Attribute("ns", "name", "value")
    assert attr.get_namespace() == "ns"
    assert attr.get_name() == "name"
    assert attr.get_value() == "value"


def test_attribute_setters() -> None:
    attr = Attribute("ns", "name", "value")
    attr.set_ns_uri("ns2")
    attr.set_name("name2")
    attr.set_value("value2")
    assert attr.get_namespace() == "ns2"
    assert attr.get_name() == "name2"
    assert attr.get_value() == "value2"


def test_attribute_pdfbox_camelcase_aliases() -> None:
    attr = Attribute("ns", "name", "value")
    attr.setNsURI("ns2")
    attr.setName("name2")
    attr.setValue("value2")

    assert attr.getNamespace() == "ns2"
    assert attr.getName() == "name2"
    assert attr.getValue() == "value2"


def test_attribute_equality_and_repr() -> None:
    a = Attribute("ns", "name", "value")
    b = Attribute("ns", "name", "value")
    c = Attribute("ns", "name", "other")
    assert a == b
    assert a != c
    assert "name=value" in repr(a)


def test_field_carries_property_name(metadata: XMPMetadata) -> None:
    field = TextType(metadata, "ns", "p", "name", "v")
    assert field.get_property_name() == "name"
    field.set_property_name("renamed")
    assert field.get_property_name() == "renamed"


def test_field_pdfbox_camelcase_property_aliases(metadata: XMPMetadata) -> None:
    field = TextType(metadata, "ns", "p", "name", "v")
    field.setPropertyName("renamed")

    assert field.getPropertyName() == "renamed"


def test_field_attribute_round_trip(metadata: XMPMetadata) -> None:
    field = TextType(metadata, "ns", "p", "name", "v")
    attr = Attribute("http://x/", "lang", "en-US")
    field.set_attribute(attr)
    assert field.contains_attribute("lang") is True
    assert field.get_attribute("lang") is attr
    assert attr in field.get_all_attributes()
    field.remove_attribute("lang")
    assert field.contains_attribute("lang") is False
    assert field.get_attribute("lang") is None


def test_field_pdfbox_camelcase_attribute_aliases(metadata: XMPMetadata) -> None:
    field = TextType(metadata, "ns", "p", "name", "v")
    attr = Attribute("http://x/", "lang", "en-US")
    field.setAttribute(attr)

    assert field.containsAttribute("lang") is True
    assert field.getAttribute("lang") is attr
    assert attr in field.getAllAttributes()
    field.removeAttribute("lang")
    assert field.containsAttribute("lang") is False


def test_field_attribute_replaces_by_name(metadata: XMPMetadata) -> None:
    field = TextType(metadata, "ns", "p", "name", "v")
    field.set_attribute(Attribute("a", "x", "1"))
    field.set_attribute(Attribute("b", "x", "2"))
    assert field.get_attribute("x").get_value() == "2"
    assert len(field.get_all_attributes()) == 1


def test_field_metadata_back_reference(metadata: XMPMetadata) -> None:
    field = TextType(metadata, "ns", "p", "name", "v")
    assert field.get_metadata() is metadata
    assert field.getMetadata() is metadata

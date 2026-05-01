from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import (
    AgentNameType,
    ArrayProperty,
    BooleanType,
    Cardinality,
    ChoiceType,
    DateType,
    GUIDType,
    IntegerType,
    LangAlt,
    MIMEType,
    ProperNameType,
    RealType,
    RenditionClassType,
    ResourceEventType,
    ResourceRefType,
    TextType,
    TypeMapping,
    URIType,
    URLType,
    VersionType,
    XMPMetadata,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def mapping(metadata: XMPMetadata) -> TypeMapping:
    return TypeMapping(metadata)


def test_create_simple_types(mapping: TypeMapping) -> None:
    assert isinstance(mapping.create_text("ns", "p", "n", "s"), TextType)
    assert isinstance(mapping.create_integer("ns", "p", "n", 1), IntegerType)
    assert isinstance(mapping.create_boolean("ns", "p", "n", True), BooleanType)
    assert isinstance(
        mapping.create_date("ns", "p", "n", datetime(2024, 1, 1, tzinfo=UTC)),
        DateType,
    )
    assert isinstance(mapping.create_real("ns", "p", "n", 1.5), RealType)
    assert isinstance(mapping.create_uri("ns", "p", "n", "u"), URIType)
    assert isinstance(mapping.create_url("ns", "p", "n", "u"), URLType)
    assert isinstance(
        mapping.create_rendition_class("ns", "p", "n", "s"), RenditionClassType
    )
    assert isinstance(mapping.create_proper_name("ns", "p", "n", "s"), ProperNameType)
    assert isinstance(mapping.create_agent_name("ns", "p", "n", "s"), AgentNameType)
    assert isinstance(mapping.create_mime_type("ns", "p", "n", "s"), MIMEType)
    assert isinstance(mapping.create_guid("ns", "p", "n", "s"), GUIDType)
    assert isinstance(mapping.create_choice("ns", "p", "n", "s"), ChoiceType)


def test_metadata_back_reference(metadata: XMPMetadata, mapping: TypeMapping) -> None:
    assert mapping.get_metadata() is metadata
    text = mapping.create_text("ns", "p", "n", "s")
    assert text.get_metadata() is metadata


def test_create_array_and_lang_alt(mapping: TypeMapping) -> None:
    arr = mapping.create_array_property("ns", "p", "n", Cardinality.Bag)
    assert isinstance(arr, ArrayProperty)
    assert arr.get_array_type() is Cardinality.Bag
    la = mapping.create_lang_alt("ns", "p", "n")
    assert isinstance(la, LangAlt)
    assert la.get_array_type() is Cardinality.Alt


@pytest.mark.parametrize(
    "type_name,value,expected_cls",
    [
        ("Text", "hello", TextType),
        ("Integer", 5, IntegerType),
        ("Boolean", True, BooleanType),
        ("Real", 1.5, RealType),
        ("URI", "https://example.com/", URIType),
        ("URL", "https://example.com/", URLType),
        ("ProperName", "Bob", ProperNameType),
        ("AgentName", "agent", AgentNameType),
        ("MIMEType", "image/png", MIMEType),
        ("RenditionClass", "default", RenditionClassType),
        ("GUID", "abc-123", GUIDType),
        ("Choice", "x", ChoiceType),
    ],
)
def test_instanciate_simple_property_dispatches(
    mapping: TypeMapping, type_name: str, value: object, expected_cls: type
) -> None:
    prop = mapping.instanciate_simple_property("ns", "p", "n", value, type_name)
    assert isinstance(prop, expected_cls)


def test_instanciate_simple_property_unknown_raises(mapping: TypeMapping) -> None:
    with pytest.raises(ValueError):
        mapping.instanciate_simple_property("ns", "p", "n", "v", "BogusType")


def test_instanciate_simple_property_propagates_value_error(mapping: TypeMapping) -> None:
    with pytest.raises(ValueError):
        mapping.instanciate_simple_property("ns", "p", "n", "Not an int", "Integer")


def test_is_simple_type_known(mapping: TypeMapping) -> None:
    assert mapping.is_simple_type_known("Text") is True
    assert mapping.is_simple_type_known("Bogus") is False


def test_instanciate_structured_type_dispatches_version(
    mapping: TypeMapping,
) -> None:
    prop = mapping.instanciate_structured_type("Version", "Versions")
    assert isinstance(prop, VersionType)
    assert prop.get_metadata() is mapping.get_metadata()
    assert prop.get_property_name() == "Versions"


def test_version_structured_type_is_known(mapping: TypeMapping) -> None:
    assert mapping.is_structured_type_known("Version") is True
    assert mapping.is_structured_type_namespace(VersionType.NAMESPACE) is True


def test_existing_structured_types_still_dispatch(mapping: TypeMapping) -> None:
    assert isinstance(
        mapping.instanciate_structured_type("ResourceRef"), ResourceRefType
    )
    assert isinstance(
        mapping.instanciate_structured_type("ResourceEvent"), ResourceEventType
    )

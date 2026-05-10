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


def test_is_defined_schema_recognizes_builtin_namespaces(
    mapping: TypeMapping,
) -> None:
    # A handful of upstream-registered schema namespaces.
    assert mapping.is_defined_schema("http://ns.adobe.com/xap/1.0/") is True
    assert mapping.is_defined_schema("http://purl.org/dc/elements/1.1/") is True
    assert mapping.is_defined_schema("http://ns.adobe.com/photoshop/1.0/") is True
    assert mapping.is_defined_schema("http://ns.adobe.com/tiff/1.0/") is True
    # Unknown namespaces are not schemas.
    assert mapping.is_defined_schema("http://example.com/unknown/") is False


def test_add_new_name_space_marks_namespace_as_schema(mapping: TypeMapping) -> None:
    ns = "http://example.com/custom/"
    assert mapping.is_defined_schema(ns) is False
    mapping.add_new_name_space(ns, "cust")
    assert mapping.is_defined_schema(ns) is True
    assert mapping.is_defined_namespace(ns) is True


def test_add_new_name_space_optional_prefix(mapping: TypeMapping) -> None:
    ns = "http://example.com/np/"
    mapping.add_new_name_space(ns)
    assert mapping.is_defined_schema(ns) is True


def test_add_new_namespace_alias_still_works(mapping: TypeMapping) -> None:
    ns = "http://example.com/legacy/"
    mapping.add_new_namespace(ns, "leg")
    assert mapping.is_defined_schema(ns) is True


def test_defined_structured_types_round_trip(mapping: TypeMapping) -> None:
    ns = "http://example.com/myType/"
    assert mapping.is_defined_type("MyType") is False
    assert mapping.is_defined_type_namespace(ns) is False
    mapping.add_to_defined_structured_types("MyType", ns)
    assert mapping.is_defined_type("MyType") is True
    assert mapping.is_defined_type_namespace(ns) is True
    assert mapping.is_defined_namespace(ns) is True


def test_is_defined_namespace_covers_structured_namespaces(
    mapping: TypeMapping,
) -> None:
    # Built-in structured types like Job have their own namespace.
    job_ns = "http://ns.adobe.com/xap/1.0/sType/Job#"
    assert mapping.is_structured_type_namespace(job_ns) is True
    assert mapping.is_defined_namespace(job_ns) is True


def test_is_defined_namespace_unknown(mapping: TypeMapping) -> None:
    assert mapping.is_defined_namespace("http://nowhere.example/") is False


def test_defined_state_is_per_instance(metadata: XMPMetadata) -> None:
    """Mappings registered on one TypeMapping must not bleed into another."""
    a = TypeMapping(metadata)
    b = TypeMapping(metadata)
    a.add_new_name_space("http://example.com/iso/", "iso")
    a.add_to_defined_structured_types("Iso", "http://example.com/iso-t/")
    assert b.is_defined_schema("http://example.com/iso/") is False
    assert b.is_defined_type("Iso") is False
    assert b.is_defined_type_namespace("http://example.com/iso-t/") is False


def test_create_x_path_factory(mapping: TypeMapping) -> None:
    from pypdfbox.xmpbox.type.xpath_type import XPathType

    inst = mapping.create_x_path("http://x/", "x", "Path", "//foo")
    assert isinstance(inst, XPathType)


def test_create_xpath_alias_returns_same(mapping: TypeMapping) -> None:
    from pypdfbox.xmpbox.type.xpath_type import XPathType

    inst = mapping.create_xpath("http://x/", "x", "Path", "//bar")
    assert isinstance(inst, XPathType)


def test_initialize_resets_defined_state(mapping: TypeMapping) -> None:
    """``initialize`` rebuilds the lookup tables (mirrors upstream
    private ``initialize()`` behaviour at line 92)."""
    ns = "http://example.com/willbecleared/"
    mapping.add_new_name_space(ns, "x")
    mapping.add_to_defined_structured_types("X", "http://example.com/xt/")
    assert mapping.is_defined_schema(ns) is True
    mapping.initialize()
    assert mapping.is_defined_schema(ns) is False
    assert mapping.is_defined_type("X") is False
    # Built-in structured-type namespaces survive the reinit.
    assert mapping.is_structured_type_namespace(
        "http://ns.adobe.com/xap/1.0/sType/Job#"
    ) is True


def test_type_card_to_string_static_helpers() -> None:
    pt = TypeMapping.create_property_type("Text", Cardinality.Bag)
    assert TypeMapping.type(pt) == "Text"
    assert TypeMapping.card(pt) is Cardinality.Bag
    s = TypeMapping.to_string(pt)
    assert "Text" in s and "Bag" in s


def test_add_name_space_registers_schema_class(mapping: TypeMapping) -> None:
    """Use a synthesised schema class — built-in schemas would create
    an import cycle, so we declare a small one inline that mirrors the
    minimal ``NAMESPACE`` contract upstream's ``addNameSpace`` reads."""

    class _FakeSchema:
        NAMESPACE = "http://example.com/added-via-add-name-space/"
        _FIELD_TYPES: dict[str, str] = {}

    mapping.add_name_space(_FakeSchema)
    assert mapping.is_defined_schema(_FakeSchema.NAMESPACE) is True
    assert mapping.get_schema_factory(_FakeSchema.NAMESPACE) is not None


def test_add_name_space_requires_namespace_attribute(mapping: TypeMapping) -> None:
    class _NoNs:
        pass

    with pytest.raises(ValueError):
        mapping.add_name_space(_NoNs)


def test_get_associated_schema_object_unknown_returns_none(
    mapping: TypeMapping, metadata: XMPMetadata,
) -> None:
    assert (
        mapping.get_associated_schema_object(
            metadata, "http://example.com/unknown/", "x"
        )
        is None
    )


def test_properties_description_to_string_matches_upstream_format() -> None:
    """Mirror of upstream ``PropertiesDescription.toString()`` (Java
    lines 99-103). The textual form is the upstream
    ``PropertiesDescription{types=...}`` shape."""
    from pypdfbox.xmpbox.type.type_mapping import (
        PropertiesDescription,
        PropertyType,
    )

    desc = PropertiesDescription()
    assert desc.to_string() == "PropertiesDescription{types={}}"
    desc.add_new_property("Title", PropertyType(type="Text"))
    s = desc.to_string()
    assert s.startswith("PropertiesDescription{types=")
    assert "Title" in s
    # Stays consistent with __repr__ (upstream toString is also the only
    # textual rendering).
    assert s == repr(desc)

"""Upstream-parity tests for ``pypdfbox.xmpbox.type.TypeMapping``.

Apache PDFBox does not ship a dedicated ``TypeMappingTest.java`` — the
class is exercised indirectly via ``DomXmpParserTest`` and the various
schema tests. The cases below cover the API surfaces those tests rely on,
modelled on upstream method names and behaviours so that future re-syncs
remain diff-friendly.

Specifically these mirror behaviour of:

* ``TypeMapping.instanciateDefinedType`` — line 210
* ``TypeMapping.instanciateSimpleField`` — line 236
* ``TypeMapping.isStructuredTypeNamespace`` / ``isDefinedTypeNamespace`` /
  ``isDefinedNamespace`` — lines 252, 257, 333
* ``TypeMapping.addToDefinedStructuredTypes`` — line 144
* ``TypeMapping.getDefinedDescriptionByNamespace`` (1-arg / 2-arg) — lines 162, 176
* ``TypeMapping.getStructuredPropMapping`` — line 280
* ``TypeMapping.getSchemaFactory`` — line 316
* ``TypeMapping.getSpecifiedPropertyType`` — line 339
* ``TypeMapping.initializePropMapping`` — line 418
* ``TypeMapping.createPropertyType`` — line 529

Reference upstream file: ``xmpbox/src/main/java/org/apache/xmpbox/type/TypeMapping.java``
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    BadFieldValueException,
    DimensionsType,
    IntegerType,
    JobType,
    TextType,
    TypeMapping,
    XMPMetadata,
)
from pypdfbox.xmpbox.type.array_property import Cardinality
from pypdfbox.xmpbox.type.type_mapping import (
    DefinedStructuredType,
    PropertiesDescription,
    PropertyType,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def mapping(metadata: XMPMetadata) -> TypeMapping:
    return TypeMapping(metadata)


# --- createPropertyType (line 529) -----------------------------------


def test_create_property_type_records_type_and_default_cardinality() -> None:
    pt = TypeMapping.create_property_type("Text")
    assert pt.type == "Text"
    assert pt.card is Cardinality.Simple


def test_create_property_type_with_explicit_cardinality() -> None:
    pt = TypeMapping.create_property_type("Integer", Cardinality.Bag)
    assert pt.type == "Integer"
    assert pt.card is Cardinality.Bag


def test_create_property_type_to_string_matches_upstream_shape() -> None:
    pt = TypeMapping.create_property_type("Text", Cardinality.Simple)
    # Upstream ``toString`` returns ``{type: <type>, card: <card>}``.
    assert "type:" in str(pt) and "card:" in str(pt)
    assert "Text" in str(pt)
    assert "Simple" in str(pt)


# --- PropertiesDescription -------------------------------------------


def test_properties_description_round_trip() -> None:
    desc = PropertiesDescription()
    pt_text = TypeMapping.create_property_type("Text")
    desc.add_new_property("title", pt_text)
    assert desc.get_property_type("title") is pt_text
    assert "title" in desc.get_properties_names()
    assert desc.get_property_type("missing") is None


def test_properties_description_deprecated_alias() -> None:
    desc = PropertiesDescription()
    desc.add_new_property("a", TypeMapping.create_property_type("Text"))
    # Both upstream method names point to the same list (single-element here).
    assert desc.get_properties_name() == desc.get_properties_names() == ["a"]


# --- initializePropMapping (line 418) --------------------------------


def test_initialize_prop_mapping_for_structured_type_uses_field_types() -> None:
    desc = TypeMapping.initialize_prop_mapping(DimensionsType)
    names = desc.get_properties_names()
    assert set(names) == {"h", "w", "unit"}
    assert desc.get_property_type("h").type == "Real"
    assert desc.get_property_type("unit").type == "Text"


def test_initialize_prop_mapping_returns_empty_for_class_without_metadata() -> None:
    class _Plain:
        pass

    desc = TypeMapping.initialize_prop_mapping(_Plain)
    assert desc.get_properties_names() == []


# --- getStructuredPropMapping (line 280) -----------------------------


def test_get_structured_prop_mapping_for_known_type(
    mapping: TypeMapping,
) -> None:
    desc = mapping.get_structured_prop_mapping("Dimensions")
    assert desc is not None
    assert "h" in desc.get_properties_names()


def test_get_structured_prop_mapping_for_unknown_returns_none(
    mapping: TypeMapping,
) -> None:
    assert mapping.get_structured_prop_mapping("Bogus") is None


# --- getSchemaFactory + addNewNameSpace (lines 274, 316) -------------


def test_get_schema_factory_after_add_new_name_space(mapping: TypeMapping) -> None:
    ns = "http://example.com/iso/"
    mapping.add_new_name_space(ns, "iso")
    factory = mapping.get_schema_factory(ns)
    assert factory is not None
    assert factory.get_namespace() == ns
    # Newly added namespaces are also flagged as defined schemas.
    assert mapping.is_defined_schema(ns) is True


def test_get_schema_factory_returns_none_for_unknown_namespace(
    mapping: TypeMapping,
) -> None:
    assert mapping.get_schema_factory("http://example.com/unknown/") is None


# --- addToDefinedStructuredTypes / getDefinedDescriptionByNamespace ---


def test_add_to_defined_structured_types_with_explicit_description(
    mapping: TypeMapping,
) -> None:
    ns = "http://example.com/extType/"
    desc = PropertiesDescription()
    desc.add_new_property("foo", TypeMapping.create_property_type("Text"))
    mapping.add_to_defined_structured_types("ExtType", ns, desc)

    # Single-arg deprecated lookup returns the registered description.
    assert mapping.get_defined_description_by_namespace(ns) is desc

    # Two-arg lookup disambiguates by field name.
    assert (
        mapping.get_defined_description_by_namespace(ns, "foo") is desc
    )
    assert mapping.get_defined_description_by_namespace(ns, "missing") is None


def test_add_to_defined_structured_types_keeps_multiple_descriptions(
    mapping: TypeMapping,
) -> None:
    ns = "http://example.com/multi/"
    a = PropertiesDescription()
    a.add_new_property("alpha", TypeMapping.create_property_type("Text"))
    b = PropertiesDescription()
    b.add_new_property("beta", TypeMapping.create_property_type("Integer"))
    mapping.add_to_defined_structured_types("Alpha", ns, a)
    mapping.add_to_defined_structured_types("Beta", ns, b)

    assert mapping.get_defined_description_by_namespace(ns, "alpha") is a
    assert mapping.get_defined_description_by_namespace(ns, "beta") is b


def test_get_defined_description_by_namespace_unknown_returns_none(
    mapping: TypeMapping,
) -> None:
    assert (
        mapping.get_defined_description_by_namespace(
            "http://example.com/no-such/"
        )
        is None
    )
    assert (
        mapping.get_defined_description_by_namespace(
            "http://example.com/no-such/", "field"
        )
        is None
    )


# --- instanciateDefinedType (line 210) -------------------------------


def test_instanciate_defined_type_returns_defined_structured_type(
    mapping: TypeMapping,
) -> None:
    ns = "http://example.com/dyn/"
    inst = mapping.instanciate_defined_type("Foo", ns)
    assert isinstance(inst, DefinedStructuredType)
    assert inst.get_namespace() == ns
    assert inst.get_property_name() == "Foo"


def test_defined_structured_type_records_property_definitions(
    metadata: XMPMetadata,
) -> None:
    inst = DefinedStructuredType(metadata, "http://example.com/d/", "d", "Bar")
    pt = TypeMapping.create_property_type("Text")
    inst.add_property_definition("name", pt)
    assert inst.get_defined_properties() == {"name": pt}


# --- instanciateSimpleField (line 236) -------------------------------


def test_instanciate_simple_field_dispatches_via_class_metadata(
    mapping: TypeMapping,
) -> None:
    # DimensionsType.unit is declared as a Text field in _FIELD_TYPES.
    prop = mapping.instanciate_simple_field(
        DimensionsType, None, "stDim", "unit", "inch"
    )
    assert isinstance(prop, TextType)
    assert prop.get_string_value() == "inch"


def test_instanciate_simple_field_unknown_field_raises(
    mapping: TypeMapping,
) -> None:
    with pytest.raises(ValueError):
        mapping.instanciate_simple_field(
            DimensionsType, None, "stDim", "noSuchField", "x"
        )


# --- getSpecifiedPropertyType (line 339) -----------------------------


def test_get_specified_property_type_resolves_known_schema(
    mapping: TypeMapping,
) -> None:
    # An empty schema factory for a custom namespace; lookups should fall
    # through to the structured / defined paths.
    ns = "http://example.com/empty-schema/"
    mapping.add_new_name_space(ns, "es")
    # Empty factory -> property unknown -> not structured/defined ->
    # return None (pre PDFBOX-6133 behaviour) instead of raising.
    assert (
        mapping.get_specified_property_type((ns, "anything"), None)
        is None
    )


def test_get_specified_property_type_for_structured_namespace(
    mapping: TypeMapping,
) -> None:
    job_ns = JobType.NAMESPACE
    pt = mapping.get_specified_property_type((job_ns, "name"), None)
    assert pt is not None
    assert pt.type == "Job"
    assert pt.card is Cardinality.Simple


def test_get_specified_property_type_for_defined_namespace_returns_defined_type(
    mapping: TypeMapping,
) -> None:
    ns = "http://example.com/dynstruct/"
    desc = PropertiesDescription()
    desc.add_new_property("foo", TypeMapping.create_property_type("Text"))
    mapping.add_to_defined_structured_types("DynStruct", ns, desc)
    pt = mapping.get_specified_property_type((ns, "foo"), None)
    assert pt is not None
    assert pt.type == "DefinedType"


def test_get_specified_property_type_unknown_namespace_raises(
    mapping: TypeMapping,
) -> None:
    with pytest.raises(BadFieldValueException):
        mapping.get_specified_property_type(
            ("http://example.com/nowhere/", "x"), None
        )


# --- isStructuredTypeNamespace / isDefinedTypeNamespace --------------


def test_is_structured_type_namespace_for_built_in_struct(
    mapping: TypeMapping,
) -> None:
    assert mapping.is_structured_type_namespace(JobType.NAMESPACE) is True
    assert (
        mapping.is_structured_type_namespace("http://example.com/none/") is False
    )


def test_is_defined_type_namespace_after_registration(
    mapping: TypeMapping,
) -> None:
    ns = "http://example.com/registered/"
    assert mapping.is_defined_type_namespace(ns) is False
    mapping.add_to_defined_structured_types("Reg", ns)
    assert mapping.is_defined_type_namespace(ns) is True




# --- IntegerType sanity (mapping wires through cleanly) --------------


def test_instanciate_simple_property_integer_via_property_type(
    mapping: TypeMapping,
) -> None:
    # Round-trip: createPropertyType -> instanciateSimpleProperty using the
    # ``type`` field of the returned PropertyType.
    pt: PropertyType = TypeMapping.create_property_type("Integer")
    prop = mapping.instanciate_simple_property("ns", "p", "n", 42, pt.type)
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 42


# --- addNameSpace / addNewNameSpace (lines 267, 274) -----------------


def test_add_name_space_registers_factory_for_schema_class(
    mapping: TypeMapping,
) -> None:
    class _FakeSchema:
        NAMESPACE = "http://example.com/added-via-add-name-space/"
        _FIELD_TYPES: dict[str, str] = {"foo": "Text"}

    mapping.add_name_space(_FakeSchema)
    factory = mapping.get_schema_factory(_FakeSchema.NAMESPACE)
    assert factory is not None
    assert factory.get_namespace() == _FakeSchema.NAMESPACE
    # The properties description gathered from the class is queryable.
    assert factory.get_property_type("foo") is not None


# --- initialize (line 92) -------------------------------------------


def test_initialize_clears_user_added_state(mapping: TypeMapping) -> None:
    mapping.add_new_name_space("http://example.com/x/", "x")
    mapping.add_to_defined_structured_types("Foo", "http://example.com/foo/")
    mapping.initialize()
    assert mapping.is_defined_schema("http://example.com/x/") is False
    assert mapping.is_defined_type("Foo") is False


# --- anonymous PropertyType accessors (lines 541-555) ---------------


def test_property_type_static_accessors() -> None:
    pt = TypeMapping.create_property_type("Real", Cardinality.Bag)
    assert TypeMapping.type(pt) == "Real"
    assert TypeMapping.card(pt) is Cardinality.Bag
    assert "Real" in TypeMapping.to_string(pt)
    assert "Bag" in TypeMapping.to_string(pt)


# --- createXPath (line 519) -----------------------------------------


def test_create_x_path_returns_xpath_type(mapping: TypeMapping) -> None:
    from pypdfbox.xmpbox.type.xpath_type import XPathType

    inst = mapping.create_x_path("http://x/", "x", "P", "//e")
    assert isinstance(inst, XPathType)


# --- getAssociatedSchemaObject (line 301) ---------------------------


def test_get_associated_schema_object_for_unknown_namespace_returns_none(
    mapping: TypeMapping, metadata: XMPMetadata,
) -> None:
    assert (
        mapping.get_associated_schema_object(
            metadata, "http://example.com/unknown-ns/", "p"
        )
        is None
    )


def test_get_associated_schema_object_after_add_new_name_space(
    mapping: TypeMapping, metadata: XMPMetadata,
) -> None:
    """When the namespace is registered (even if as an empty schema)
    the method must return something non-``None`` — upstream returns
    a freshly constructed ``XMPSchema`` instance; the Python port may
    return either a schema or the schema-factory record (both convey
    that the namespace is recognised)."""
    ns = "http://example.com/registered-ns/"
    mapping.add_new_name_space(ns, "rg")
    result = mapping.get_associated_schema_object(metadata, ns, "rg")
    assert result is not None

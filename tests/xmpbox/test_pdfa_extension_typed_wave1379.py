"""Wave 1379 — PDF/A Extension schema typed nested-struct surface.

Closes the DEFERRED entry "PDFAExtensionSchema nested-struct typing for
``pdfaSchema:property`` + ``pdfaSchema:valueType``" by exercising the
typed ``PDFASchemaType`` / ``PDFAPropertyType`` / ``PDFATypeType`` /
``PDFAFieldType`` accessors on :class:`PDFAExtensionSchema`.

The pre-1379 surface stored the Bag as ``list[dict[str, str]]`` and gave
no introspection into nested ``pdfaSchema:property`` / ``pdfaSchema:valueType``
Seqs. Wave 1379 adds the typed mirror so callers can populate and read
back the full PDF/A Extension struct hierarchy without dropping down to
COS primitives.
"""
from __future__ import annotations

from pypdfbox.xmpbox import PDFAExtensionSchema, XMPMetadata
from pypdfbox.xmpbox.type.pdfa_field_description_type import PDFAFieldType
from pypdfbox.xmpbox.type.pdfa_property_type import PDFAPropertyType
from pypdfbox.xmpbox.type.pdfa_schema_type import PDFASchemaType
from pypdfbox.xmpbox.type.pdfa_type_type import PDFATypeType


def _ext() -> PDFAExtensionSchema:
    return PDFAExtensionSchema(XMPMetadata.create_xmp_metadata())


# ---------- factory shortcuts -----------------------------------------


def test_create_schema_type_returns_pdfa_schema_type_bound_to_metadata() -> None:
    schema = _ext()
    typed = schema.create_schema_type()
    assert isinstance(typed, PDFASchemaType)
    assert typed.get_metadata() is schema.get_metadata()


def test_create_property_type_returns_pdfa_property_type() -> None:
    schema = _ext()
    typed = schema.create_property_type()
    assert isinstance(typed, PDFAPropertyType)
    assert typed.get_metadata() is schema.get_metadata()


def test_create_value_type_returns_pdfa_type_type() -> None:
    schema = _ext()
    typed = schema.create_value_type()
    assert isinstance(typed, PDFATypeType)
    assert typed.get_metadata() is schema.get_metadata()


def test_create_field_type_returns_pdfa_field_type() -> None:
    schema = _ext()
    typed = schema.create_field_type()
    assert isinstance(typed, PDFAFieldType)
    assert typed.get_metadata() is schema.get_metadata()


# ---------- typed add / get round-trip --------------------------------


def _populated_schema_description(
    parent: PDFAExtensionSchema,
    *,
    schema: str,
    namespace_uri: str,
    prefix: str,
) -> PDFASchemaType:
    typed = parent.create_schema_type()
    typed.add_simple_property(PDFASchemaType.SCHEMA, schema)
    typed.add_simple_property(PDFASchemaType.NAMESPACE_URI, namespace_uri)
    typed.add_simple_property(PDFASchemaType.PREFIX, prefix)
    return typed


def test_add_schema_description_round_trips_typed_entry() -> None:
    schema = _ext()
    typed = _populated_schema_description(
        schema,
        schema="Custom Schema",
        namespace_uri="http://example.com/ns/custom/",
        prefix="custom",
    )
    schema.add_schema_description(typed)

    typed_view = schema.get_schema_descriptions()
    assert len(typed_view) == 1
    assert typed_view[0] is typed
    assert typed_view[0].get_namespace_uri() == "http://example.com/ns/custom/"
    assert typed_view[0].get_prefix_value() == "custom"


def test_add_schema_description_keeps_lite_surface_in_sync() -> None:
    """The lite ``list[dict[str, str]]`` mirror tracks typed adds so existing
    readers (:meth:`get_extension_schemas`, :meth:`get_count`) keep working
    after a typed write."""
    schema = _ext()
    typed = _populated_schema_description(
        schema,
        schema="Custom Schema",
        namespace_uri="http://example.com/ns/custom/",
        prefix="custom",
    )
    schema.add_schema_description(typed)

    entries = schema.get_extension_schemas()
    assert len(entries) == 1
    assert entries[0]["schema"] == "Custom Schema"
    assert entries[0]["namespaceURI"] == "http://example.com/ns/custom/"
    assert entries[0]["prefix"] == "custom"
    assert schema.get_count() == 1


def test_add_schema_description_returns_structure_array_name() -> None:
    """Mirrors upstream ``PDFAExtensionSchema.addSchemaDescription`` returning
    the local field name the entry is stored under — always the RDF array
    element name ``"li"``."""
    schema = _ext()
    typed = _populated_schema_description(
        schema,
        schema="Demo",
        namespace_uri="http://example.com/ns/demo/",
        prefix="demo",
    )
    assert schema.add_schema_description(typed) == "li"


def test_get_schema_descriptions_returns_defensive_copy() -> None:
    schema = _ext()
    typed = _populated_schema_description(
        schema,
        schema="Demo",
        namespace_uri="http://example.com/ns/demo/",
        prefix="demo",
    )
    schema.add_schema_description(typed)
    snapshot = schema.get_schema_descriptions()
    snapshot.clear()
    # Internal store untouched.
    assert len(schema.get_schema_descriptions()) == 1


def test_lite_add_does_not_populate_typed_mirror() -> None:
    """The pre-1379 lite path stays an opt-in stub: typed callers must
    explicitly populate the typed mirror via :meth:`add_schema_description`."""
    schema = _ext()
    schema.add_extension_schema(
        "Lite", "http://example.com/ns/lite/", "lite"
    )
    assert schema.get_extension_schemas() == [
        {
            "schema": "Lite",
            "namespaceURI": "http://example.com/ns/lite/",
            "prefix": "lite",
        }
    ]
    assert schema.get_schema_descriptions() == []
    assert schema.get_typed_schemas() == []


# ---------- nested property descriptions ------------------------------


def test_nested_property_descriptions_round_trip() -> None:
    schema = _ext()
    typed = _populated_schema_description(
        schema,
        schema="Demo",
        namespace_uri="http://example.com/ns/demo/",
        prefix="demo",
    )
    prop = schema.create_property_type()
    prop.add_simple_property(PDFAPropertyType.NAME, "weight")
    prop.add_simple_property(PDFAPropertyType.VALUETYPE, "Real")
    prop.add_simple_property(PDFAPropertyType.CATEGORY, "external")
    prop.add_simple_property(PDFAPropertyType.DESCRIPTION, "Object weight in kg")
    typed.add_property_description(prop)
    schema.add_schema_description(typed)

    fetched = schema.get_schema_descriptions()[0]
    properties = fetched.get_property_descriptions()
    assert len(properties) == 1
    assert properties[0].get_name() == "weight"
    assert properties[0].get_value_type() == "Real"
    assert properties[0].get_category() == "external"
    assert properties[0].get_description() == "Object weight in kg"


def test_nested_value_type_with_fields_round_trip() -> None:
    schema = _ext()
    typed = _populated_schema_description(
        schema,
        schema="Demo",
        namespace_uri="http://example.com/ns/demo/",
        prefix="demo",
    )

    value_type = schema.create_value_type()
    value_type.add_simple_property(PDFATypeType.TYPE, "Address")
    value_type.add_simple_property(
        PDFATypeType.NS_URI, "http://example.com/ns/demo/address/"
    )
    value_type.add_simple_property(PDFATypeType.PREFIX, "addr")
    value_type.add_simple_property(PDFATypeType.DESCRIPTION, "A postal address")

    street_field = schema.create_field_type()
    street_field.add_simple_property(PDFAFieldType.NAME, "street")
    street_field.add_simple_property(PDFAFieldType.VALUETYPE, "Text")
    street_field.add_simple_property(
        PDFAFieldType.DESCRIPTION, "Street name + number"
    )
    value_type.add_field_description(street_field)

    city_field = schema.create_field_type()
    city_field.add_simple_property(PDFAFieldType.NAME, "city")
    city_field.add_simple_property(PDFAFieldType.VALUETYPE, "Text")
    value_type.add_field_description(city_field)

    typed.add_value_type_description(value_type)
    schema.add_schema_description(typed)

    fetched = schema.get_schema_descriptions()[0]
    types = fetched.get_value_type_descriptions()
    assert len(types) == 1
    assert types[0].get_type() == "Address"
    assert types[0].get_prefix_value() == "addr"
    assert types[0].get_namespace_uri() == "http://example.com/ns/demo/address/"

    fields = types[0].get_field_descriptions()
    assert len(fields) == 2
    assert fields[0].get_name() == "street"
    assert fields[0].get_value_type() == "Text"
    assert fields[0].get_description() == "Street name + number"
    assert fields[1].get_name() == "city"


# ---------- lookup helpers --------------------------------------------


def test_find_schema_by_namespace_returns_matching_typed_entry() -> None:
    schema = _ext()
    first = _populated_schema_description(
        schema,
        schema="First",
        namespace_uri="http://example.com/ns/first/",
        prefix="first",
    )
    second = _populated_schema_description(
        schema,
        schema="Second",
        namespace_uri="http://example.com/ns/second/",
        prefix="second",
    )
    schema.add_schema_description(first)
    schema.add_schema_description(second)

    found = schema.find_schema_by_namespace("http://example.com/ns/second/")
    assert found is second
    assert schema.find_schema_by_namespace("http://example.com/ns/none/") is None


def test_find_schema_by_prefix_returns_matching_typed_entry() -> None:
    schema = _ext()
    first = _populated_schema_description(
        schema,
        schema="First",
        namespace_uri="http://example.com/ns/first/",
        prefix="first",
    )
    second = _populated_schema_description(
        schema,
        schema="Second",
        namespace_uri="http://example.com/ns/second/",
        prefix="second",
    )
    schema.add_schema_description(first)
    schema.add_schema_description(second)

    assert schema.find_schema_by_prefix("first") is first
    assert schema.find_schema_by_prefix("none") is None


# ---------- multiple typed adds maintain ordering ---------------------


def test_multiple_typed_adds_preserve_insertion_order() -> None:
    schema = _ext()
    for i in range(3):
        entry = _populated_schema_description(
            schema,
            schema=f"S{i}",
            namespace_uri=f"http://example.com/ns/{i}/",
            prefix=f"p{i}",
        )
        schema.add_schema_description(entry)

    typed_view = schema.get_schema_descriptions()
    assert [e.get_prefix_value() for e in typed_view] == ["p0", "p1", "p2"]
    lite_view = schema.get_extension_schemas()
    assert [e["prefix"] for e in lite_view] == ["p0", "p1", "p2"]
    assert schema.get_count() == 3

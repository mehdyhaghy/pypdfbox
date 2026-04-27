from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    AbstractStructuredType,
    ArrayProperty,
    Cardinality,
    PDFAPropertyType,
    PDFASchemaType,
    PDFATypeType,
    TextType,
    URIType,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_is_structured_type(metadata: XMPMetadata) -> None:
    schema = PDFASchemaType(metadata)
    assert isinstance(schema, AbstractStructuredType)


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    schema = PDFASchemaType(metadata)
    assert schema.get_namespace() == "http://www.aiim.org/pdfa/ns/schema#"
    assert schema.get_prefix() == "pdfaSchema"


def test_field_constants() -> None:
    assert PDFASchemaType.SCHEMA == "schema"
    assert PDFASchemaType.NAMESPACE_URI == "namespaceURI"
    assert PDFASchemaType.PREFIX == "prefix"
    assert PDFASchemaType.PROPERTY == "property"
    assert PDFASchemaType.VALUE_TYPE == "valueType"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    schema = PDFASchemaType(metadata)
    assert schema.get_namespace_uri() is None
    assert schema.get_prefix_value() is None
    assert schema.get_property_array() is None
    assert schema.get_value_type() is None


def test_set_simple_fields(metadata: XMPMetadata) -> None:
    schema = PDFASchemaType(metadata)
    schema.add_simple_property(PDFASchemaType.SCHEMA, "My Custom Schema")
    schema.add_simple_property(
        PDFASchemaType.NAMESPACE_URI, "http://example.com/ns#"
    )
    schema.add_simple_property(PDFASchemaType.PREFIX, "mycs")

    assert schema.get_namespace_uri() == "http://example.com/ns#"
    assert schema.get_prefix_value() == "mycs"

    sch_prop = schema.get_property(PDFASchemaType.SCHEMA)
    assert isinstance(sch_prop, TextType)
    assert sch_prop.get_string_value() == "My Custom Schema"

    ns_prop = schema.get_property(PDFASchemaType.NAMESPACE_URI)
    assert isinstance(ns_prop, URIType)


def test_property_seq_population(metadata: XMPMetadata) -> None:
    schema = PDFASchemaType(metadata)
    seq = ArrayProperty(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        PDFASchemaType.PROPERTY,
        Cardinality.Seq,
    )
    schema.add_property(seq)

    pprop = PDFAPropertyType(metadata)
    pprop.add_simple_property(PDFAPropertyType.NAME, "foo")
    seq.add_property(pprop)

    arr = schema.get_property_array()
    assert isinstance(arr, ArrayProperty)
    assert len(arr.get_all_properties()) == 1


def test_value_type_seq_population(metadata: XMPMetadata) -> None:
    schema = PDFASchemaType(metadata)
    seq = ArrayProperty(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        PDFASchemaType.VALUE_TYPE,
        Cardinality.Seq,
    )
    schema.add_property(seq)

    vt = PDFATypeType(metadata)
    vt.add_simple_property(PDFATypeType.TYPE, "MyType")
    seq.add_property(vt)

    arr = schema.get_value_type()
    assert isinstance(arr, ArrayProperty)
    assert len(arr.get_all_properties()) == 1

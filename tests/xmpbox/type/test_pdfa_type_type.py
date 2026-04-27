from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    AbstractStructuredType,
    ArrayProperty,
    Cardinality,
    PDFAFieldType,
    PDFATypeType,
    PDFAValueTypeDescriptionType,
    TextType,
    URIType,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_is_structured_type(metadata: XMPMetadata) -> None:
    pt = PDFATypeType(metadata)
    assert isinstance(pt, AbstractStructuredType)


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    pt = PDFATypeType(metadata)
    assert pt.get_namespace() == "http://www.aiim.org/pdfa/ns/type#"
    assert pt.get_prefix() == "pdfaType"


def test_field_constants() -> None:
    assert PDFATypeType.TYPE == "type"
    assert PDFATypeType.NS_URI == "namespaceURI"
    assert PDFATypeType.PREFIX == "prefix"
    assert PDFATypeType.DESCRIPTION == "description"
    assert PDFATypeType.FIELD == "field"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    pt = PDFATypeType(metadata)
    assert pt.get_type() is None
    assert pt.get_namespace_uri() is None
    assert pt.get_prefix_value() is None
    assert pt.get_description() is None
    assert pt.get_fields() is None


def test_set_simple_fields(metadata: XMPMetadata) -> None:
    pt = PDFATypeType(metadata)
    pt.add_simple_property(PDFATypeType.TYPE, "MyType")
    pt.add_simple_property(PDFATypeType.NS_URI, "http://example.com/types#")
    pt.add_simple_property(PDFATypeType.PREFIX, "mt")
    pt.add_simple_property(PDFATypeType.DESCRIPTION, "describes MyType")

    assert pt.get_type() == "MyType"
    assert pt.get_namespace_uri() == "http://example.com/types#"
    assert pt.get_prefix_value() == "mt"
    assert pt.get_description() == "describes MyType"

    assert isinstance(pt.get_property(PDFATypeType.TYPE), TextType)
    assert isinstance(pt.get_property(PDFATypeType.NS_URI), URIType)


def test_field_seq_population(metadata: XMPMetadata) -> None:
    pt = PDFATypeType(metadata)
    seq = ArrayProperty(
        metadata,
        pt.get_namespace(),
        pt.get_prefix(),
        PDFATypeType.FIELD,
        Cardinality.Seq,
    )
    pt.add_property(seq)

    f = PDFAFieldType(metadata)
    f.add_simple_property(PDFAFieldType.NAME, "fieldA")
    seq.add_property(f)

    arr = pt.get_fields()
    assert isinstance(arr, ArrayProperty)
    assert len(arr.get_all_properties()) == 1


def test_value_type_description_alias_is_pdfatypetype() -> None:
    # The alias module re-exports the canonical class — same identity.
    assert PDFAValueTypeDescriptionType is PDFATypeType

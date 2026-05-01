from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    AbstractStructuredType,
    ChoiceType,
    PDFAFieldDescriptionType,
    PDFAFieldType,
    TextType,
)
from pypdfbox.xmpbox.type.pdfa_field_description_type import (
    PDFAFieldDescriptionType as DirectFieldAlias,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_is_structured_type(metadata: XMPMetadata) -> None:
    field = PDFAFieldType(metadata)
    assert isinstance(field, AbstractStructuredType)


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    field = PDFAFieldType(metadata)
    assert field.get_namespace() == "http://www.aiim.org/pdfa/ns/field#"
    assert field.get_prefix() == "pdfaField"
    assert field.get_prefered_prefix() == "pdfaField"


def test_field_constants() -> None:
    assert PDFAFieldType.NAME == "name"
    assert PDFAFieldType.VALUETYPE == "valueType"
    assert PDFAFieldType.DESCRIPTION == "description"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    field = PDFAFieldType(metadata)
    assert field.get_name() is None
    assert field.get_value_type() is None
    assert field.get_description() is None


def test_set_and_get_name(metadata: XMPMetadata) -> None:
    field = PDFAFieldType(metadata)
    field.add_simple_property(PDFAFieldType.NAME, "x")
    assert field.get_name() == "x"
    assert isinstance(field.get_property(PDFAFieldType.NAME), TextType)


def test_set_and_get_value_type(metadata: XMPMetadata) -> None:
    field = PDFAFieldType(metadata)
    field.add_simple_property(PDFAFieldType.VALUETYPE, "Integer")
    assert field.get_value_type() == "Integer"
    assert isinstance(field.get_property(PDFAFieldType.VALUETYPE), ChoiceType)


def test_set_and_get_description(metadata: XMPMetadata) -> None:
    field = PDFAFieldType(metadata)
    field.add_simple_property(PDFAFieldType.DESCRIPTION, "an integer field")
    assert field.get_description() == "an integer field"


def test_field_type_table() -> None:
    assert PDFAFieldType._FIELD_TYPES == {
        "name": "Text",
        "valueType": "Choice",
        "description": "Text",
    }


def test_field_description_alias_is_pdfa_field_type() -> None:
    # Symmetric to ``PDFAValueTypeDescriptionType is PDFATypeType``: the
    # schema-level descriptive name resolves to the canonical class so
    # ``isinstance`` semantics are preserved across both spellings.
    assert PDFAFieldDescriptionType is PDFAFieldType


def test_direct_field_description_alias_is_pdfa_field_type() -> None:
    assert DirectFieldAlias is PDFAFieldType


def test_field_description_alias_instance_is_pdfa_field_type(
    metadata: XMPMetadata,
) -> None:
    inst = PDFAFieldDescriptionType(metadata)
    assert isinstance(inst, PDFAFieldType)
    assert inst.get_namespace() == "http://www.aiim.org/pdfa/ns/field#"
    assert inst.get_prefix() == "pdfaField"


def test_module_all_exports_alias() -> None:
    from pypdfbox.xmpbox.type import pdfa_field_description_type as mod

    assert "PDFAFieldDescriptionType" in mod.__all__
    assert "PDFAFieldType" in mod.__all__

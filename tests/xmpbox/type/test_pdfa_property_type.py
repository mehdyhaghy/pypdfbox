from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import (
    AbstractStructuredType,
    ChoiceType,
    PDFAPropertyType,
    TextType,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_is_structured_type(metadata: XMPMetadata) -> None:
    prop = PDFAPropertyType(metadata)
    assert isinstance(prop, AbstractStructuredType)


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    prop = PDFAPropertyType(metadata)
    assert prop.get_namespace() == "http://www.aiim.org/pdfa/ns/property#"
    assert prop.get_prefix() == "pdfaProperty"


def test_field_constants() -> None:
    assert PDFAPropertyType.NAME == "name"
    assert PDFAPropertyType.VALUETYPE == "valueType"
    assert PDFAPropertyType.CATEGORY == "category"
    assert PDFAPropertyType.DESCRIPTION == "description"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    prop = PDFAPropertyType(metadata)
    assert prop.get_name() is None
    assert prop.get_value_type() is None
    assert prop.get_category() is None
    assert prop.get_description() is None


def test_set_and_get_each_field(metadata: XMPMetadata) -> None:
    prop = PDFAPropertyType(metadata)
    prop.add_simple_property(PDFAPropertyType.NAME, "MyProp")
    prop.add_simple_property(PDFAPropertyType.VALUETYPE, "Text")
    prop.add_simple_property(PDFAPropertyType.CATEGORY, "external")
    prop.add_simple_property(PDFAPropertyType.DESCRIPTION, "describes MyProp")

    assert prop.get_name() == "MyProp"
    assert prop.get_value_type() == "Text"
    assert prop.get_category() == "external"
    assert prop.get_description() == "describes MyProp"


def test_value_type_is_choice_typed(metadata: XMPMetadata) -> None:
    prop = PDFAPropertyType(metadata)
    prop.add_simple_property(PDFAPropertyType.VALUETYPE, "URI")
    assert isinstance(prop.get_property(PDFAPropertyType.VALUETYPE), ChoiceType)


def test_category_is_choice_typed(metadata: XMPMetadata) -> None:
    prop = PDFAPropertyType(metadata)
    prop.add_simple_property(PDFAPropertyType.CATEGORY, "internal")
    assert isinstance(prop.get_property(PDFAPropertyType.CATEGORY), ChoiceType)


def test_name_is_text_typed(metadata: XMPMetadata) -> None:
    prop = PDFAPropertyType(metadata)
    prop.add_simple_property(PDFAPropertyType.NAME, "X")
    val = prop.get_property(PDFAPropertyType.NAME)
    assert isinstance(val, TextType)

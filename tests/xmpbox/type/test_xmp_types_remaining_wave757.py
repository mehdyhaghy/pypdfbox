from __future__ import annotations

from datetime import date, datetime

import pytest

from pypdfbox.xmpbox import (
    AbstractField,
    AbstractSimpleProperty,
    AbstractStructuredType,
    ArrayProperty,
    Attribute,
    Cardinality,
    GPSCoordinateType,
    LayerType,
    RationalType,
    TextType,
    TypeMapping,
    XMPMetadata,
)
from pypdfbox.xmpbox.type import PDFAPropertyType, PDFASchemaType, PDFATypeType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_gps_coordinate_parse_rejects_bad_dm_parts(
    metadata: XMPMetadata,
) -> None:
    assert GPSCoordinateType(metadata, None, None, "gps", "12,badN").parse() is None
    assert GPSCoordinateType(metadata, None, None, "gps", "12,60N").parse() is None
    assert GPSCoordinateType(metadata, None, None, "gps", "1,2,3,4N").parse() is None


def test_gps_coordinate_format_dm_rejects_unknown_hemisphere() -> None:
    with pytest.raises(ValueError, match="hemisphere"):
        GPSCoordinateType.format_dm(12, 30.5, "Q")


def test_layer_name_property_none_removes_existing_name(
    metadata: XMPMetadata,
) -> None:
    layer = LayerType(metadata)
    layer.set_layer_name("Visible")

    layer.set_layer_name_property(None)

    assert layer.get_layer_name() is None
    assert layer.get_layer_name_property() is None
    assert layer.get_property(LayerType.LAYER_NAME) is None


def test_attribute_hash_and_non_attribute_equality() -> None:
    attr = Attribute("ns", "name", "value")

    assert attr.__eq__(object()) is NotImplemented
    assert hash(attr) == hash(Attribute("ns", "name", "value"))


def test_abstract_field_cannot_instantiate_directly(
    metadata: XMPMetadata,
) -> None:
    # AbstractField is an ABC with abstract get_namespace/get_prefix —
    # mirrors upstream ``public abstract class AbstractField`` and the two
    # abstract accessors on it.
    del metadata
    with pytest.raises(TypeError):
        AbstractField(object(), "field")  # type: ignore[abstract]


@pytest.mark.parametrize(
    "method_name",
    ["set_value", "get_string_value", "get_value"],
)
def test_abstract_simple_property_methods_are_abstract(method_name: str) -> None:
    # The three accessors are abstract in upstream Java; concrete
    # simple-property subclasses (Boolean/Integer/Real/Text/Date) implement
    # them. Verify the base class advertises them as abstract.
    assert method_name in AbstractSimpleProperty.__abstractmethods__


def test_pdfa_schema_empty_description_lists(metadata: XMPMetadata) -> None:
    schema = PDFASchemaType(metadata)

    assert schema.get_property_descriptions() == []
    assert schema.get_value_type_descriptions() == []


def test_pdfa_schema_reuses_existing_property_and_value_type_sequences(
    metadata: XMPMetadata,
) -> None:
    schema = PDFASchemaType(metadata)
    prop = PDFAPropertyType(metadata)
    value_type = PDFATypeType(metadata)

    schema.add_property_description(prop)
    prop_seq = schema.get_property_array()
    schema.add_property_description(PDFAPropertyType(metadata))

    schema.add_value_type_description(value_type)
    value_type_seq = schema.get_value_type()
    schema.add_value_type_description(PDFATypeType(metadata))

    assert schema.get_property_array() is prop_seq
    assert schema.get_value_type() is value_type_seq
    assert len(schema.get_property_descriptions()) == 2
    assert len(schema.get_value_type_descriptions()) == 2


def test_array_property_same_property_none_names_and_complex_identity(
    metadata: XMPMetadata,
) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)

    left_none = TextType(metadata, "ns", "p", None, "a")
    right_none = TextType(metadata, "ns", "p", None, "b")
    named = TextType(metadata, "ns", "p", "name", "a")
    complex_left = ArrayProperty(metadata, "ns", "p", "nested", Cardinality.Seq)
    complex_right = ArrayProperty(metadata, "ns", "p", "nested", Cardinality.Seq)

    assert arr.is_same_property(left_none, right_none) is True
    assert arr.is_same_property(left_none, named) is False
    assert arr.is_same_property(complex_left, complex_left) is True
    assert arr.is_same_property(complex_left, complex_right) is False


def test_type_mapping_unknown_structured_type_and_rational_factory(
    metadata: XMPMetadata,
) -> None:
    mapping = TypeMapping(metadata)

    with pytest.raises(ValueError, match="Unknown structured"):
        mapping.instanciate_structured_type("MissingType")

    rational = mapping.create_rational("ns", "p", "ratio", "1/2")
    assert isinstance(rational, RationalType)
    assert rational.as_fraction() is not None


def test_abstract_structured_type_conversion_helpers(
    metadata: XMPMetadata,
) -> None:
    structured = LayerType(metadata)

    assert AbstractStructuredType._is_calendar_like(datetime(2024, 1, 2)) is True
    assert AbstractStructuredType._is_calendar_like(date(2024, 1, 2)) is True
    assert AbstractStructuredType._is_calendar_like("2024-01-02") is False

    attr = structured._new_attribute("ns", "name", "value")
    assert attr == Attribute("ns", "name", "value")

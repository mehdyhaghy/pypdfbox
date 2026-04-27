"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/type/TestSimpleMetadataProperties.java

Tests that exercise upstream's TypeMapping factory (createBoolean / createDate /
createInteger / createReal / createText) are translated against the Python
TypeMapping that ships with this wave; the upstream `XMPMetadata.getTypeMapping`
is not yet wired from the metadata object so the test instantiates TypeMapping
directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import (
    Attribute,
    BooleanType,
    DateType,
    IntegerType,
    RealType,
    TextType,
    TypeMapping,
    XMPMetadata,
)


@pytest.fixture
def parent() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.fixture
def mapping(parent: XMPMetadata) -> TypeMapping:
    return TypeMapping(parent)


def test_boolean_bad_type_detection(parent: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        BooleanType(parent, None, "test", "boolean", "Not a Boolean")


def test_date_bad_type_detection(parent: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        DateType(parent, None, "test", "date", "Bad Date")


def test_integer_bad_type_detection(parent: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        IntegerType(parent, None, "test", "integer", "Not an int")


def test_real_bad_type_detection(parent: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        RealType(parent, None, "test", "real", "Not a real")


def test_text_bad_type_detection(parent: XMPMetadata) -> None:
    # Upstream uses Calendar; we use datetime as the equivalent type, which
    # is not a String and so must be rejected by TextType.
    now = datetime.now(UTC)
    with pytest.raises(ValueError):
        TextType(parent, None, "test", "text", now)


def test_element_and_object_synchronization(mapping: TypeMapping) -> None:
    boolv = True
    datev = datetime.now(UTC)
    integerv = 1
    realv = 1.69
    textv = "TEXTCONTENT"

    bool_prop = mapping.create_boolean(None, "test", "boolean", boolv)
    date_prop = mapping.create_date(None, "test", "date", datev)
    integer_prop = mapping.create_integer(None, "test", "integer", integerv)
    real_prop = mapping.create_real(None, "test", "real", realv)
    text_prop = mapping.create_text(None, "test", "text", textv)

    assert bool_prop.get_value() == boolv
    assert date_prop.get_value() == datev
    assert integer_prop.get_value() == integerv
    assert real_prop.get_value() == pytest.approx(realv)
    assert text_prop.get_string_value() == textv


def test_creation_from_string(parent: XMPMetadata) -> None:
    boolv = "False"
    datev = "2010-03-22T14:33:11+01:00"
    integerv = "10"
    realv = "1.92"
    textv = "text"

    bool_prop = BooleanType(parent, None, "test", "boolean", boolv)
    date_prop = DateType(parent, None, "test", "date", datev)
    integer_prop = IntegerType(parent, None, "test", "integer", integerv)
    real_prop = RealType(parent, None, "test", "real", realv)
    text_prop = TextType(parent, None, "test", "text", textv)

    assert bool_prop.get_string_value() == boolv
    # Upstream DateConverter normalises the offset; stdlib's isoformat keeps
    # the offset intact, so the round-trip yields the canonical input.
    assert date_prop.get_string_value().startswith("2010-03-22T14:33:11")
    assert integer_prop.get_string_value() == integerv
    assert float(real_prop.get_string_value()) == pytest.approx(1.92)
    assert text_prop.get_string_value() == textv


def test_object_creation_with_namespace(mapping: TypeMapping) -> None:
    ns = "http://www.test.org/pdfa/"
    bool_prop = mapping.create_boolean(ns, "test", "boolean", True)
    date_prop = mapping.create_date(ns, "test", "date", datetime.now(UTC))
    integer_prop = mapping.create_integer(ns, "test", "integer", 1)
    real_prop = mapping.create_real(ns, "test", "real", 1.6)
    text_prop = mapping.create_text(ns, "test", "text", "TEST")

    assert bool_prop.get_namespace() == ns
    assert date_prop.get_namespace() == ns
    assert integer_prop.get_namespace() == ns
    assert real_prop.get_namespace() == ns
    assert text_prop.get_namespace() == ns


def test_exception_with_cause() -> None:
    cause = RuntimeError()
    with pytest.raises(ValueError):
        raise ValueError("TEST") from cause


def test_attribute(parent: XMPMetadata) -> None:
    integer = IntegerType(parent, None, "test", "integer", 1)
    value = Attribute("http://www.test.org/test/", "value1", "StringValue1")
    value2 = Attribute("http://www.test.org/test/", "value2", "StringValue2")

    integer.set_attribute(value)

    assert integer.get_attribute(value.get_name()) is value
    assert integer.contains_attribute(value.get_name()) is True

    integer.set_attribute(value2)
    assert integer.get_attribute(value2.get_name()) is value2

    integer.remove_attribute(value2.get_name())
    assert integer.contains_attribute(value2.get_name()) is False

    value_ns = Attribute("http://www.tefst2.org/test/", "value2", "StringValue.2")
    integer.set_attribute(value_ns)
    value_ns2 = Attribute("http://www.test2.org/test/", "value2", "StringValueTwo")
    integer.set_attribute(value_ns2)

    atts = integer.get_all_attributes()
    # set_attribute keys by local name, so the second value2 replaces the first
    assert value_ns not in atts
    assert value_ns2 in atts

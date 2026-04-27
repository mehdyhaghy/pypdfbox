from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    IntegerType,
    TextType,
    XMPMetadata,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.mark.parametrize(
    "card", [Cardinality.Bag, Cardinality.Seq, Cardinality.Alt]
)
def test_array_property_carries_cardinality(metadata: XMPMetadata, card: Cardinality) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", card)
    assert arr.get_array_type() is card
    assert arr.get_array_type().is_array() is True


def test_simple_cardinality_is_not_array() -> None:
    assert Cardinality.Simple.is_array() is False


def test_array_append_and_iterate(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    arr.add_property(TextType(metadata, "ns", "p", "li", "one"))
    arr.add_property(TextType(metadata, "ns", "p", "li", "two"))
    arr.add_property(TextType(metadata, "ns", "p", "li", "three"))
    items = arr.get_elements_as_string()
    assert items == ["one", "two", "three"]


def test_array_remove_property(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Seq)
    a = TextType(metadata, "ns", "p", "li", "a")
    b = TextType(metadata, "ns", "p", "li", "b")
    arr.add_property(a)
    arr.add_property(b)
    arr.remove_property(a)
    assert arr.get_elements_as_string() == ["b"]
    arr.remove_property(a)  # idempotent (mirror upstream silent miss)


def test_array_namespace_prefix(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    assert arr.get_namespace() == "ns"
    assert arr.get_prefix() == "p"
    assert arr.get_property_name() == "items"


def test_array_holds_mixed_simple_property_types(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Seq)
    arr.add_property(IntegerType(metadata, "ns", "p", "li", 1))
    arr.add_property(TextType(metadata, "ns", "p", "li", "two"))
    elements = arr.get_elements_as_string()
    assert elements == ["1", "two"]

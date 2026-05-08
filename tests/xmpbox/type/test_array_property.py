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


def test_cardinality_pdfbox_camelcase_alias() -> None:
    assert Cardinality.Bag.isArray() is True
    assert Cardinality.Simple.isArray() is False


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


def test_get_properties_by_local_name_returns_none_when_empty(
    metadata: XMPMetadata,
) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    assert arr.get_properties_by_local_name("missing") is None


def test_get_properties_by_local_name_filters_by_local_name(
    metadata: XMPMetadata,
) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    a = TextType(metadata, "ns", "p", "alpha", "1")
    b = TextType(metadata, "ns", "p", "beta", "2")
    c = TextType(metadata, "ns", "p", "alpha", "3")
    arr.add_property(a)
    arr.add_property(b)
    arr.add_property(c)
    matches = arr.get_properties_by_local_name("alpha")
    assert matches == [a, c]
    assert arr.get_properties_by_local_name("beta") == [b]
    assert arr.get_properties_by_local_name("missing") is None


def test_get_property_returns_first_match(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    first = TextType(metadata, "ns", "p", "alpha", "first")
    second = TextType(metadata, "ns", "p", "alpha", "second")
    arr.add_property(first)
    arr.add_property(second)
    assert arr.get_property("alpha") is first
    assert arr.get_property("missing") is None


def test_get_array_property_returns_only_array_children(
    metadata: XMPMetadata,
) -> None:
    outer = ArrayProperty(metadata, "ns", "p", "outer", Cardinality.Bag)
    inner = ArrayProperty(metadata, "ns", "p", "nested", Cardinality.Seq)
    text = TextType(metadata, "ns", "p", "scalar", "leaf")
    outer.add_property(inner)
    outer.add_property(text)
    assert outer.get_array_property("nested") is inner
    # scalar field exists but is not an array — upstream casts and crashes;
    # we choose to return None instead (documented in the docstring).
    assert outer.get_array_property("scalar") is None
    assert outer.get_array_property("missing") is None


def test_namespace_prefix_map_round_trip(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    assert arr.get_all_namespaces_with_prefix() == {}
    arr.add_namespace("http://example.com/ns/", "ex")
    arr.add_namespace("http://example.com/other/", None)
    assert arr.get_namespace_prefix("http://example.com/ns/") == "ex"
    # None prefix is normalised to empty string, mirroring the structured-type
    # base class behaviour.
    assert arr.get_namespace_prefix("http://example.com/other/") == ""
    assert arr.get_namespace_prefix("http://example.com/missing/") is None
    full = arr.get_all_namespaces_with_prefix()
    assert full == {
        "http://example.com/ns/": "ex",
        "http://example.com/other/": "",
    }


def test_get_all_namespaces_with_prefix_is_live_view(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    view = arr.get_all_namespaces_with_prefix()
    arr.add_namespace("http://example.com/ns/", "ex")
    # Mirrors upstream's getAllNamespacesWithPrefix which exposes the backing map.
    assert view["http://example.com/ns/"] == "ex"


def test_remove_properties_by_name_drops_all_matches(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    arr.add_property(TextType(metadata, "ns", "p", "name", "a"))
    arr.add_property(TextType(metadata, "ns", "p", "name", "b"))
    arr.add_property(IntegerType(metadata, "ns", "p", "other", 1))
    arr.remove_properties_by_name("name")
    assert [p.get_property_name() for p in arr.get_all_properties()] == ["other"]


def test_remove_properties_by_name_empty_is_noop(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    arr.remove_properties_by_name("missing")
    assert arr.get_all_properties() == []


def test_is_same_property_class_and_value(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    a = TextType(metadata, "ns", "p", "name", "x")
    b = TextType(metadata, "ns", "p", "name", "x")
    diff_class = IntegerType(metadata, "ns", "p", "name", 0)
    assert arr.is_same_property(a, b) is True
    assert arr.is_same_property(a, diff_class) is False


def test_contains_property_round_trip(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    a = TextType(metadata, "ns", "p", "tag", "x")
    arr.add_property(a)
    assert arr.contains_property(TextType(metadata, "ns", "p", "tag", "x")) is True
    assert arr.contains_property(TextType(metadata, "ns", "p", "tag", "y")) is False


def test_array_property_pdfbox_camelcase_aliases(metadata: XMPMetadata) -> None:
    arr = ArrayProperty(metadata, "ns", "p", "items", Cardinality.Bag)
    first = TextType(metadata, "ns", "p", "li", "one")
    second = TextType(metadata, "ns", "p", "li", "two")

    assert arr.getNamespace() == "ns"
    assert arr.getPrefix() == "p"
    arr.addProperty(first)
    arr.addProperty(second)

    assert arr.getAllProperties() == [first, second]
    assert arr.getPropertiesByLocalName("li") == [first, second]
    assert arr.getProperty("li") is first
    assert arr.containsProperty(TextType(metadata, "ns", "p", "li", "one")) is True
    assert arr.isSameProperty(first, TextType(metadata, "ns", "p", "li", "one")) is True

    arr.addNamespace("http://example.com/ns/", "ex")
    assert arr.getNamespacePrefix("http://example.com/ns/") == "ex"
    assert arr.getAllNamespacesWithPrefix()["http://example.com/ns/"] == "ex"

    arr.removeProperty(first)
    assert arr.getAllProperties() == [second]
    arr.removePropertiesByName("li")
    assert arr.getAllProperties() == []


def test_array_property_get_array_property_camelcase_alias(
    metadata: XMPMetadata,
) -> None:
    outer = ArrayProperty(metadata, "ns", "p", "outer", Cardinality.Bag)
    inner = ArrayProperty(metadata, "ns", "p", "nested", Cardinality.Seq)
    outer.addProperty(inner)

    assert outer.getArrayProperty("nested") is inner
    assert outer.getArrayProperty("missing") is None

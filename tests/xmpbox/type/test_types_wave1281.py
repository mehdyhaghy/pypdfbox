"""Tests for the ``xmpbox.type.Types`` enum + container classes."""

from __future__ import annotations

from pypdfbox.xmpbox.type import (
    AbstractComplexProperty,
    ComplexPropertyContainer,
    Types,
)
from pypdfbox.xmpbox.type.abstract_field import AbstractField


class _SimpleField(AbstractField):
    def __init__(self, name: str, value: str = ""):
        super().__init__(None, name)
        self._value = value

    def get_namespace(self) -> str | None:
        return None

    def get_prefix(self) -> str | None:
        return None


def test_types_text_is_simple_basic() -> None:
    assert Types.Text.is_simple()
    assert Types.Text.is_basic()
    assert Types.Text.get_implementing_class_name() == "TextType"


def test_types_uri_inherits_text() -> None:
    assert Types.URI.is_simple()
    assert Types.URI.get_basic() is Types.Text
    assert not Types.URI.is_basic()


def test_types_dimensions_is_structured() -> None:
    assert Types.Dimensions.is_structured()
    assert not Types.Dimensions.is_simple()


def test_types_defined_flag() -> None:
    assert Types.DefinedType.is_defined()
    assert not Types.Text.is_defined()


def test_complex_property_container_add_remove() -> None:
    cpc = ComplexPropertyContainer()
    f1 = _SimpleField("title", "hello")
    f2 = _SimpleField("title", "world")
    cpc.add_property(f1)
    cpc.add_property(f2)
    # add_property removes prior identical-by-reference then appends; since
    # both are different instances, both are present.
    assert len(cpc.get_all_properties()) == 2
    listed = cpc.get_properties_by_local_name("title")
    assert listed is not None
    assert len(listed) == 2
    cpc.remove_property(f1)
    assert len(cpc.get_all_properties()) == 1
    cpc.remove_properties_by_name("title")
    assert cpc.get_all_properties() == []


def test_complex_property_container_get_first_equivalent_property() -> None:
    cpc = ComplexPropertyContainer()
    f = _SimpleField("subject")
    cpc.add_property(f)
    found = cpc.get_first_equivalent_property("subject", _SimpleField)
    assert found is f
    assert cpc.get_first_equivalent_property("missing", _SimpleField) is None


class _Complex(AbstractComplexProperty):
    def get_namespace(self) -> str | None:
        return None

    def get_prefix(self) -> str | None:
        return None


def test_abstract_complex_property_namespace_map() -> None:
    prop = _Complex(None, "root")
    prop.add_namespace("http://example.com/", "ex")
    assert prop.get_namespace_prefix("http://example.com/") == "ex"
    assert "http://example.com/" in prop.get_all_namespaces_with_prefix()


def test_abstract_complex_property_add_replaces_same_name() -> None:
    prop = _Complex(None, "root")
    f1 = _SimpleField("title", "a")
    f2 = _SimpleField("title", "b")
    prop.add_property(f1)
    prop.add_property(f2)
    listed = prop.get_all_properties()
    assert len(listed) == 1
    assert listed[0] is f2


def test_abstract_complex_property_get_property_returns_first() -> None:
    prop = _Complex(None, "root")
    f = _SimpleField("title", "v")
    prop.add_property(f)
    assert prop.get_property("title") is f
    assert prop.get_property("missing") is None

"""Coverage-boost for ``pypdfbox.xmpbox.type.abstract_complex_property``
(wave 1321).

Targets the previously-untested branches:

* ``remove_property`` — delegation to the inner container.
* ``get_container`` — container accessor.
* ``get_array_property`` — both the array-hit and non-array-hit arms, plus
  the missing-name short-circuit.
* ``get_first_equivalent_property`` — delegation through the container.
"""

from __future__ import annotations

from pypdfbox.xmpbox.type.abstract_complex_property import AbstractComplexProperty
from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
from pypdfbox.xmpbox.type.complex_property_container import ComplexPropertyContainer
from pypdfbox.xmpbox.type.integer_type import IntegerType
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


class _Concrete(AbstractComplexProperty):
    """Concrete AbstractComplexProperty for direct testing.

    The base class is abstract because it inherits ``AbstractField``'s
    ``get_namespace`` / ``get_prefix`` abstract methods. We fill them with
    no-ops here.
    """

    def __init__(self, metadata: XMPMetadata, property_name: str | None) -> None:
        super().__init__(metadata, property_name)

    def get_namespace(self) -> str | None:
        return "http://example.org/ns/"

    def get_prefix(self) -> str | None:
        return "ex"


def _meta() -> XMPMetadata:
    return XMPMetadata()


def _text(name: str | None, value: str = "v") -> TextType:
    return TextType(_meta(), "http://example.org/ns/", "ex", name, value)


def _integer(name: str | None, value: int = 0) -> IntegerType:
    return IntegerType(_meta(), "http://example.org/ns/", "ex", name, value)


def test_get_container_returns_internal_container() -> None:
    prop = _Concrete(_meta(), "p")
    container = prop.get_container()
    assert isinstance(container, ComplexPropertyContainer)
    # Mutating through ``add_property`` should be visible through the
    # accessor — same identity, not a copy.
    prop.add_property(_text("foo"))
    assert len(container.get_all_properties()) == 1


def test_remove_property_delegates_to_container() -> None:
    prop = _Concrete(_meta(), "p")
    child = _text("foo")
    prop.add_property(child)
    assert prop.get_property("foo") is child
    prop.remove_property(child)
    assert prop.get_property("foo") is None


def test_get_array_property_returns_array_when_match() -> None:
    prop = _Concrete(_meta(), "p")
    arr = ArrayProperty(
        _meta(), "http://example.org/ns/", "ex", "tags", Cardinality.Bag
    )
    prop.add_property(arr)
    assert prop.get_array_property("tags") is arr


def test_get_array_property_returns_none_when_not_array() -> None:
    prop = _Concrete(_meta(), "p")
    prop.add_property(_text("foo", "bar"))
    # Property exists but is not an ArrayProperty -> None.
    assert prop.get_array_property("foo") is None


def test_get_array_property_returns_none_when_missing() -> None:
    prop = _Concrete(_meta(), "p")
    assert prop.get_array_property("absent") is None


def test_get_first_equivalent_property_returns_typed_match() -> None:
    prop = _Concrete(_meta(), "p")
    text_a = _text("foo", "x")
    text_b = _text("foo", "y")
    prop.add_property(text_a)
    prop.add_property(text_b)
    # Latest add replaces prior same-name (non-array container semantics).
    first = prop.get_first_equivalent_property("foo", TextType)
    assert isinstance(first, TextType)


def test_get_first_equivalent_property_returns_none_when_type_mismatch() -> None:
    prop = _Concrete(_meta(), "p")
    prop.add_property(_text("foo", "v"))
    assert prop.get_first_equivalent_property("foo", IntegerType) is None


def test_get_first_equivalent_property_returns_none_when_missing() -> None:
    prop = _Concrete(_meta(), "p")
    assert prop.get_first_equivalent_property("absent", TextType) is None


def test_namespace_prefix_round_trip() -> None:
    prop = _Concrete(_meta(), "p")
    prop.add_namespace("http://example.org/a/", "a")
    prop.add_namespace("http://example.org/b/", "b")
    assert prop.get_namespace_prefix("http://example.org/a/") == "a"
    assert prop.get_namespace_prefix("http://example.org/b/") == "b"
    # Unknown -> None.
    assert prop.get_namespace_prefix("http://example.org/unknown/") is None
    table = prop.get_all_namespaces_with_prefix()
    assert table == {
        "http://example.org/a/": "a",
        "http://example.org/b/": "b",
    }


def test_get_all_properties_reflects_container_state() -> None:
    prop = _Concrete(_meta(), "p")
    assert prop.get_all_properties() == []
    child = _text("foo")
    prop.add_property(child)
    all_props = prop.get_all_properties()
    assert len(all_props) == 1
    assert all_props[0] is child

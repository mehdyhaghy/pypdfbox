"""Coverage-boost for ``pypdfbox.xmpbox.type.complex_property_container``
(wave 1320).

Targets the previously-untested branches:

* ``get_first_equivalent_property`` — type-match against the first hit.
* ``is_same_property`` — type-mismatch, both-names-None, names-differ,
  identical instances.
* ``contains_property`` — positive + negative arms.
* ``remove_properties_by_name`` — empty container short-circuit and the
  no-matching-name short-circuit.
"""

from __future__ import annotations

from pypdfbox.xmpbox.type.complex_property_container import ComplexPropertyContainer
from pypdfbox.xmpbox.type.integer_type import IntegerType
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


def _meta() -> XMPMetadata:
    return XMPMetadata()


def _text(name: str | None, value: str = "v") -> TextType:
    return TextType(_meta(), "ns", "p", name, value)


def _integer(name: str | None, value: int = 0) -> IntegerType:
    return IntegerType(_meta(), "ns", "p", name, value)


def test_get_first_equivalent_property_matches_first_of_type() -> None:
    container = ComplexPropertyContainer()
    a = _text("foo", "v1")
    b = _text("foo", "v2")
    container.add_property(a)
    container.add_property(b)
    # Different type — no match.
    assert container.get_first_equivalent_property("foo", IntegerType) is None
    # Same type — first entry wins.
    assert container.get_first_equivalent_property("foo", TextType) is a


def test_get_first_equivalent_property_missing_name_returns_none() -> None:
    container = ComplexPropertyContainer()
    container.add_property(_text("foo"))
    assert container.get_first_equivalent_property("bar", TextType) is None


def test_is_same_property_type_mismatch_returns_false() -> None:
    container = ComplexPropertyContainer()
    text = _text("foo")
    integer = _integer("foo")
    assert container.is_same_property(text, integer) is False


def test_is_same_property_both_names_none_and_equal_returns_true() -> None:
    container = ComplexPropertyContainer()
    a = _text(None)
    # Names are both None and a == a; the underscore-fall-through asserts True.
    assert container.is_same_property(a, a) is True


def test_is_same_property_one_name_none_one_not_returns_false() -> None:
    container = ComplexPropertyContainer()
    a = _text(None)
    b = _text("foo")
    # pn1 is None, pn2 is not — function returns ``pn2 is None`` -> False.
    assert container.is_same_property(a, b) is False


def test_is_same_property_names_differ_returns_false() -> None:
    container = ComplexPropertyContainer()
    a = _text("foo")
    b = _text("bar")
    assert container.is_same_property(a, b) is False


def test_is_same_property_identical_instances_returns_true() -> None:
    container = ComplexPropertyContainer()
    a = _text("foo")
    # Same type + same name + identical reference satisfies ``a == a``.
    assert container.is_same_property(a, a) is True


def test_contains_property_positive() -> None:
    container = ComplexPropertyContainer()
    a = _text("foo")
    container.add_property(a)
    assert container.contains_property(a) is True


def test_contains_property_negative() -> None:
    container = ComplexPropertyContainer()
    container.add_property(_text("foo"))
    other = _text("foo")
    # Different instance — TextType doesn't override __eq__, so the
    # identity comparison in ``is_same_property`` rejects ``other``.
    assert container.contains_property(other) is False


def test_remove_properties_by_name_short_circuits_on_empty_container() -> None:
    container = ComplexPropertyContainer()
    # Should not raise even though the container is empty.
    container.remove_properties_by_name("foo")
    assert container.get_all_properties() == []


def test_remove_properties_by_name_short_circuits_when_no_match() -> None:
    container = ComplexPropertyContainer()
    survivor = _text("keep")
    container.add_property(survivor)
    container.remove_properties_by_name("absent")
    assert container.get_all_properties() == [survivor]


def test_remove_properties_by_name_removes_all_matches() -> None:
    container = ComplexPropertyContainer()
    keep = _text("keep")
    drop1 = _text("drop")
    drop2 = _text("drop")
    container.add_property(keep)
    container.add_property(drop1)
    container.add_property(drop2)
    container.remove_properties_by_name("drop")
    assert container.get_all_properties() == [keep]


def test_add_property_replaces_existing_identical_reference() -> None:
    """``add_property`` first removes the same reference, then appends —
    the result is the value moved to the tail of the list."""
    container = ComplexPropertyContainer()
    a = _text("a")
    b = _text("b")
    container.add_property(a)
    container.add_property(b)
    # Re-add ``a`` — it should now be the last element.
    container.add_property(a)
    assert container.get_all_properties() == [b, a]


def test_get_properties_by_local_name_returns_none_on_no_match() -> None:
    container = ComplexPropertyContainer()
    container.add_property(_text("foo"))
    assert container.get_properties_by_local_name("absent") is None

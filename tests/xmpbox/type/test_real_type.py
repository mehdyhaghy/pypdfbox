from __future__ import annotations

import pytest

from pypdfbox.xmpbox import RealType, XMPMetadata
from pypdfbox.xmpbox.type import TypeMapping
from pypdfbox.xmpbox.type.abstract_simple_property import AbstractSimpleProperty


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_real_is_simple_property() -> None:
    # Upstream RealType extends AbstractSimpleProperty; the port preserves it.
    assert issubclass(RealType, AbstractSimpleProperty)


def test_real_from_float(metadata: XMPMetadata) -> None:
    field = RealType(metadata, "ns", "p", "ratio", 1.25)
    assert field.get_value() == pytest.approx(1.25)
    assert float(field.get_string_value()) == pytest.approx(1.25)


def test_real_from_int(metadata: XMPMetadata) -> None:
    # The Python port accepts int as a numeric source; upstream Java only
    # accepts Float, but in Python int and float share the numeric tower
    # (this deviation is documented in CHANGES.md).
    field = RealType(metadata, "ns", "p", "ratio", 3)
    assert field.get_value() == pytest.approx(3.0)


def test_real_from_string(metadata: XMPMetadata) -> None:
    field = RealType(metadata, "ns", "p", "ratio", "1.92")
    assert field.get_value() == pytest.approx(1.92)


def test_real_rejects_bool(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        RealType(metadata, "ns", "p", "ratio", True)


def test_real_rejects_garbage_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        RealType(metadata, "ns", "p", "ratio", "not a number")


def test_real_rejects_other_types(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        RealType(metadata, "ns", "p", "ratio", object())


def test_real_namespace_and_prefix(metadata: XMPMetadata) -> None:
    field = RealType(metadata, "http://ns/", "pre", "ratio", 2.5)
    assert field.get_namespace() == "http://ns/"
    assert field.get_prefix() == "pre"
    assert field.get_property_name() == "ratio"


def test_real_raw_value_preserved(metadata: XMPMetadata) -> None:
    # Upstream stores the original constructor argument as rawValue.
    field = RealType(metadata, "ns", "p", "ratio", "1.92")
    assert field.get_raw_value() == "1.92"


def test_real_set_value_replaces(metadata: XMPMetadata) -> None:
    field = RealType(metadata, "ns", "p", "ratio", 1.0)
    field.set_value(4.5)
    assert field.get_value() == pytest.approx(4.5)


def test_real_repr_matches_upstream_to_string(metadata: XMPMetadata) -> None:
    # Upstream AbstractSimpleProperty#toString:
    # "[" + propertyName + "=" + simpleClassName + ":" + stringValue + "]"
    field = RealType(metadata, "ns", "p", "ratio", 1.5)
    assert repr(field) == f"[ratio=RealType:{field.get_string_value()}]"


def test_real_registry_returns_real_type(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "ratio", "1.5", "Real"
    )
    assert isinstance(instance, RealType)


def test_create_real_factory(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.create_real("ns", "p", "ratio", 6.28)
    assert isinstance(instance, RealType)
    assert instance.get_value() == pytest.approx(6.28)

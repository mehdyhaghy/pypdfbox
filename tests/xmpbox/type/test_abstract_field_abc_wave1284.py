"""Wave 1284 — verify AbstractField / AbstractSimpleProperty are ABCs."""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type.abstract_field import AbstractField
from pypdfbox.xmpbox.type.abstract_simple_property import AbstractSimpleProperty
from pypdfbox.xmpbox.type.boolean_type import BooleanType


def test_abstract_field_is_abstract() -> None:
    # Mirrors upstream ``public abstract class AbstractField``.
    assert "get_namespace" in AbstractField.__abstractmethods__
    assert "get_prefix" in AbstractField.__abstractmethods__


def test_abstract_simple_property_is_abstract() -> None:
    # Mirrors upstream ``public abstract class AbstractSimpleProperty``.
    assert "set_value" in AbstractSimpleProperty.__abstractmethods__
    assert "get_string_value" in AbstractSimpleProperty.__abstractmethods__
    assert "get_value" in AbstractSimpleProperty.__abstractmethods__


def test_cannot_instantiate_abstract_field() -> None:
    with pytest.raises(TypeError):
        AbstractField(None, "name")  # type: ignore[abstract]


def test_cannot_instantiate_abstract_simple_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    with pytest.raises(TypeError):
        AbstractSimpleProperty(metadata, "ns", "p", "name", "v")  # type: ignore[abstract]


def test_boolean_type_concretely_overrides() -> None:
    # The concrete subclass must satisfy the abstract API.
    metadata = XMPMetadata.create_xmp_metadata()
    bool_prop = BooleanType(metadata, "ns", "p", "active", True)
    assert bool_prop.get_value() is True
    assert bool_prop.get_string_value() == "True"
    assert bool_prop.get_namespace() == "ns"
    assert bool_prop.get_prefix() == "p"

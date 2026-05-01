from __future__ import annotations

import pytest

from pypdfbox.xmpbox import ChoiceType, TextType, XMPMetadata
from pypdfbox.xmpbox.type import TypeMapping


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_choice_is_text_subclass() -> None:
    # Upstream ChoiceType extends TextType; the port preserves that hierarchy.
    assert issubclass(ChoiceType, TextType)


def test_choice_round_trip(metadata: XMPMetadata) -> None:
    field = ChoiceType(metadata, "ns", "p", "color", "red")
    assert field.get_value() == "red"
    assert field.get_string_value() == "red"
    assert field.get_namespace() == "ns"
    assert field.get_prefix() == "p"
    assert field.get_property_name() == "color"


def test_choice_raw_value_preserved(metadata: XMPMetadata) -> None:
    field = ChoiceType(metadata, "ns", "p", "color", "blue")
    assert field.get_raw_value() == "blue"


def test_choice_rejects_non_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        ChoiceType(metadata, "ns", "p", "color", 7)


def test_choice_set_value_replaces(metadata: XMPMetadata) -> None:
    field = ChoiceType(metadata, "ns", "p", "color", "red")
    field.set_value("green")
    assert field.get_value() == "green"


def test_choice_registry_returns_choice_type(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "color", "amber", "Choice"
    )
    assert isinstance(instance, ChoiceType)


def test_create_choice_factory(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.create_choice("ns", "p", "color", "violet")
    assert isinstance(instance, ChoiceType)
    assert instance.get_value() == "violet"

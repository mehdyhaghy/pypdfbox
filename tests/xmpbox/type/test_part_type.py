from __future__ import annotations

import pytest

from pypdfbox.xmpbox import PartType, TextType, XMPMetadata
from pypdfbox.xmpbox.type import TypeMapping


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_part_is_text_subclass() -> None:
    assert issubclass(PartType, TextType)


def test_part_round_trip(metadata: XMPMetadata) -> None:
    p = PartType(metadata, "ns", "p", "part", "section-1")
    assert p.get_value() == "section-1"
    assert p.get_string_value() == "section-1"
    assert p.get_namespace() == "ns"
    assert p.get_prefix() == "p"
    assert p.get_property_name() == "part"


def test_part_rejects_non_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        PartType(metadata, "ns", "p", "part", 1)


def test_part_registry_returns_part_type(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "part", "chapter-2", "Part"
    )
    assert isinstance(instance, PartType)


def test_create_part_factory(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.create_part("ns", "p", "part", "intro")
    assert isinstance(instance, PartType)
    assert instance.get_value() == "intro"

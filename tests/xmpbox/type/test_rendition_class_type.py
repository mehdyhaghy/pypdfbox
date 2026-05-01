from __future__ import annotations

import pytest

from pypdfbox.xmpbox import RenditionClassType, TextType, XMPMetadata
from pypdfbox.xmpbox.type import TypeMapping


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_rendition_class_is_text_subclass() -> None:
    assert issubclass(RenditionClassType, TextType)


def test_rendition_class_round_trip(metadata: XMPMetadata) -> None:
    rc = RenditionClassType(metadata, "ns", "p", "rendition", "default")
    assert rc.get_value() == "default"
    assert rc.get_string_value() == "default"
    assert rc.get_namespace() == "ns"
    assert rc.get_prefix() == "p"
    assert rc.get_property_name() == "rendition"


def test_rendition_class_rejects_non_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        RenditionClassType(metadata, "ns", "p", "rendition", 0)


def test_rendition_class_registry_returns_specific_type(
    metadata: XMPMetadata,
) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "rendition", "thumbnail:jpeg", "RenditionClass"
    )
    assert isinstance(instance, RenditionClassType)


def test_create_rendition_class_factory(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.create_rendition_class("ns", "p", "rendition", "screen")
    assert isinstance(instance, RenditionClassType)
    assert instance.get_value() == "screen"

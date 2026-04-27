from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import LayerType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    assert layer.get_namespace() == "http://ns.adobe.com/photoshop/1.0/"
    assert layer.get_prefix() == "photoshop"


def test_parse_type_attribute_set(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    attr = layer.get_attribute("parseType")
    assert attr is not None
    assert attr.get_value() == "Resource"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    assert layer.get_layer_name() is None
    assert layer.get_layer_text() is None


def test_set_and_get_layer_fields(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    layer.set_layer_name("Headline")
    layer.set_layer_text("Big news today!")
    assert layer.get_layer_name() == "Headline"
    assert layer.get_layer_text() == "Big news today!"


def test_field_constants() -> None:
    assert LayerType.LAYER_NAME == "LayerName"
    assert LayerType.LAYER_TEXT == "LayerText"

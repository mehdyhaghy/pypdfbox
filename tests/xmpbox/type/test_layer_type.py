from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import LayerType, TextType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    """
    Mirrors upstream ``@StructuredType(preferedPrefix = "stLyr",
    namespace = "http://ns.adobe.com/photoshop/1.0/Layer#")`` annotation on
    ``LayerType``.
    """
    layer = LayerType(metadata)
    assert layer.get_namespace() == "http://ns.adobe.com/photoshop/1.0/Layer#"
    assert layer.get_prefix() == "stLyr"
    assert layer.get_preferred_prefix() == "stLyr"


def test_class_namespace_constants() -> None:
    assert LayerType.NAMESPACE == "http://ns.adobe.com/photoshop/1.0/Layer#"
    assert LayerType.PREFERRED_PREFIX == "stLyr"


def test_parse_type_attribute_set(metadata: XMPMetadata) -> None:
    """Upstream constructor installs ``rdf:parseType="Resource"``."""
    layer = LayerType(metadata)
    attr = layer.get_attribute("parseType")
    assert attr is not None
    assert attr.get_value() == "Resource"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    assert layer.get_layer_name() is None
    assert layer.get_layer_text() is None
    assert layer.get_layer_name_property() is None
    assert layer.get_layer_text_property() is None


def test_set_and_get_layer_fields(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    layer.set_layer_name("Headline")
    layer.set_layer_text("Big news today!")
    assert layer.get_layer_name() == "Headline"
    assert layer.get_layer_text() == "Big news today!"


def test_field_constants() -> None:
    assert LayerType.LAYER_NAME == "LayerName"
    assert LayerType.LAYER_TEXT == "LayerText"


def test_field_type_registry_text() -> None:
    """Both fields are registered as ``Text`` per upstream ``@PropertyType``."""
    assert LayerType._FIELD_TYPES[LayerType.LAYER_NAME] == "Text"
    assert LayerType._FIELD_TYPES[LayerType.LAYER_TEXT] == "Text"


def test_set_layer_name_uses_text_type(metadata: XMPMetadata) -> None:
    """``add_simple_property`` must dispatch to ``TextType`` per ``_FIELD_TYPES``."""
    layer = LayerType(metadata)
    layer.set_layer_name("Top Layer")
    prop = layer.get_property(LayerType.LAYER_NAME)
    assert isinstance(prop, TextType)
    assert prop.get_string_value() == "Top Layer"
    assert prop.get_property_name() == LayerType.LAYER_NAME


def test_set_layer_text_uses_text_type(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    layer.set_layer_text("Hello")
    prop = layer.get_property(LayerType.LAYER_TEXT)
    assert isinstance(prop, TextType)
    assert prop.get_string_value() == "Hello"
    assert prop.get_property_name() == LayerType.LAYER_TEXT


def test_set_layer_name_replaces_existing(metadata: XMPMetadata) -> None:
    """``add_simple_property`` (via ``add_property``) replaces same-name slots."""
    layer = LayerType(metadata)
    layer.set_layer_name("First")
    layer.set_layer_name("Second")
    assert layer.get_layer_name() == "Second"
    matches = [
        p
        for p in layer.get_all_properties()
        if p.get_property_name() == LayerType.LAYER_NAME
    ]
    assert len(matches) == 1


def test_typed_property_setter_round_trip(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    text = TextType(
        metadata,
        LayerType.NAMESPACE,
        LayerType.PREFERRED_PREFIX,
        LayerType.LAYER_NAME,
        "Typed",
    )
    layer.set_layer_name_property(text)
    same = layer.get_layer_name_property()
    assert same is text
    assert layer.get_layer_name() == "Typed"


def test_typed_property_setter_none_removes(metadata: XMPMetadata) -> None:
    layer = LayerType(metadata)
    layer.set_layer_text("present")
    assert layer.get_layer_text() == "present"
    layer.set_layer_text_property(None)
    assert layer.get_layer_text() is None
    assert layer.get_layer_text_property() is None


def test_typed_property_getter_returns_none_for_wrong_slot(
    metadata: XMPMetadata,
) -> None:
    layer = LayerType(metadata)
    assert layer.get_layer_name_property() is None

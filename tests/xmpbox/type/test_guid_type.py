from __future__ import annotations

import pytest

from pypdfbox.xmpbox import GUIDType, TextType, XMPMetadata
from pypdfbox.xmpbox.type import TypeMapping


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_guid_is_text_subclass() -> None:
    # Upstream GUIDType extends TextType; the port preserves that hierarchy.
    assert issubclass(GUIDType, TextType)


def test_guid_round_trip(metadata: XMPMetadata) -> None:
    guid = "uuid:0d35e5e9-87a3-4d1b-8df9-1c34d0d11111"
    field = GUIDType(metadata, "ns", "p", "id", guid)
    assert field.get_value() == guid
    assert field.get_string_value() == guid
    assert field.get_namespace() == "ns"
    assert field.get_prefix() == "p"
    assert field.get_property_name() == "id"


def test_guid_raw_value_preserved(metadata: XMPMetadata) -> None:
    guid = "uuid:abcdef01-2345-6789-abcd-ef0123456789"
    field = GUIDType(metadata, "ns", "p", "id", guid)
    assert field.get_raw_value() == guid


def test_guid_rejects_non_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        GUIDType(metadata, "ns", "p", "id", 12345)


def test_guid_set_value_replaces(metadata: XMPMetadata) -> None:
    field = GUIDType(metadata, "ns", "p", "id", "uuid:first")
    field.set_value("uuid:second")
    assert field.get_value() == "uuid:second"


def test_guid_registry_returns_guid_type(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "id", "uuid:0000-1111", "GUID"
    )
    assert isinstance(instance, GUIDType)


def test_create_guid_factory(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.create_guid("ns", "p", "id", "uuid:abc")
    assert isinstance(instance, GUIDType)
    assert instance.get_value() == "uuid:abc"

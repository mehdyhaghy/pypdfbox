from __future__ import annotations

import pytest

from pypdfbox.xmpbox import TextType, URLType, XMPMetadata
from pypdfbox.xmpbox.type import TypeMapping


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_url_is_text_subclass() -> None:
    assert issubclass(URLType, TextType)


def test_url_round_trip(metadata: XMPMetadata) -> None:
    url = URLType(metadata, "ns", "p", "ref", "https://example.com/x")
    assert url.get_value() == "https://example.com/x"
    assert url.get_string_value() == "https://example.com/x"
    assert url.get_namespace() == "ns"
    assert url.get_prefix() == "p"
    assert url.get_property_name() == "ref"


def test_url_rejects_non_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        URLType(metadata, "ns", "p", "ref", 42)


def test_url_registry_returns_url_type(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "ref", "https://example.com", "URL"
    )
    assert isinstance(instance, URLType)


def test_create_url_factory(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.create_url("ns", "p", "ref", "https://example.com")
    assert isinstance(instance, URLType)
    assert instance.get_value() == "https://example.com"

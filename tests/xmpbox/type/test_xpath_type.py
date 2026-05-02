from __future__ import annotations

import pytest

from pypdfbox.xmpbox import TextType, XMPMetadata, XPathType
from pypdfbox.xmpbox.type import TypeMapping


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_xpath_is_text_subclass() -> None:
    assert issubclass(XPathType, TextType)


def test_xpath_round_trip(metadata: XMPMetadata) -> None:
    xp = XPathType(metadata, "ns", "p", "path", "/a/b[1]")
    assert xp.get_value() == "/a/b[1]"
    assert xp.get_string_value() == "/a/b[1]"
    assert xp.get_namespace() == "ns"
    assert xp.get_prefix() == "p"
    assert xp.get_property_name() == "path"


def test_xpath_rejects_non_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        XPathType(metadata, "ns", "p", "path", 7)


def test_xpath_registry_returns_xpath_type(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.instanciate_simple_property(
        "ns", "p", "path", "/x/y", "XPath"
    )
    assert isinstance(instance, XPathType)


def test_create_xpath_factory(metadata: XMPMetadata) -> None:
    mapping = TypeMapping(metadata)
    instance = mapping.create_xpath("ns", "p", "path", "//foo")
    assert isinstance(instance, XPathType)
    assert instance.get_value() == "//foo"

"""Wave 1275 — explicit ``to_string()`` parity for AbstractSimpleProperty."""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import TextType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_to_string_matches_upstream_format(metadata: XMPMetadata) -> None:
    prop = TextType(metadata, "ns", "p", "MyProp", "the-value")
    assert prop.to_string() == "[MyProp=TextType:the-value]"


def test_str_delegates_to_to_string(metadata: XMPMetadata) -> None:
    prop = TextType(metadata, "ns", "p", "Foo", "bar")
    assert str(prop) == prop.to_string()
    assert str(prop) == "[Foo=TextType:bar]"


def test_repr_delegates_to_to_string(metadata: XMPMetadata) -> None:
    prop = TextType(metadata, "ns", "p", "Bar", "x")
    assert repr(prop) == prop.to_string()

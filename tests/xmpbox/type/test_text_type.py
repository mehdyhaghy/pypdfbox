from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    AgentNameType,
    ChoiceType,
    GUIDType,
    MIMEType,
    ProperNameType,
    TextType,
    URIType,
    XMPMetadata,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_text_type_round_trip(metadata: XMPMetadata) -> None:
    text = TextType(metadata, "ns", "p", "title", "hello")
    assert text.get_value() == "hello"
    assert text.get_string_value() == "hello"
    assert text.get_namespace() == "ns"
    assert text.get_prefix() == "p"
    assert text.get_property_name() == "title"


def test_text_type_rejects_non_string(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        TextType(metadata, "ns", "p", "title", 123)


def test_text_type_set_value_replaces(metadata: XMPMetadata) -> None:
    text = TextType(metadata, "ns", "p", "title", "a")
    text.set_value("b")
    assert text.get_value() == "b"


def test_text_type_raw_value_preserved(metadata: XMPMetadata) -> None:
    text = TextType(metadata, "ns", "p", "title", "raw")
    assert text.get_raw_value() == "raw"


@pytest.mark.parametrize(
    "cls",
    [URIType, ProperNameType, AgentNameType, MIMEType, GUIDType, ChoiceType],
)
def test_text_subclasses_inherit_validation(metadata: XMPMetadata, cls: type) -> None:
    inst = cls(metadata, "ns", "p", "n", "abc")
    assert inst.get_string_value() == "abc"
    with pytest.raises(ValueError):
        cls(metadata, "ns", "p", "n", 42)


def test_text_repr_contains_class_and_value(metadata: XMPMetadata) -> None:
    text = TextType(metadata, "ns", "p", "title", "v")
    assert "TextType" in repr(text)
    assert "v" in repr(text)

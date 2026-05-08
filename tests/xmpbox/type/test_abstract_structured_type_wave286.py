from __future__ import annotations

from pypdfbox.xmpbox import TextType, XMPMetadata
from pypdfbox.xmpbox.type.abstract_structured_type import AbstractStructuredType


class _Struct(AbstractStructuredType):
    NAMESPACE = "http://example.com/ns#"
    PREFERRED_PREFIX = "ex"


def test_structured_type_has_property_and_clear_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    structured = _Struct(metadata, property_name="container")
    keep = TextType(metadata, "http://example.com/ns#", "ex", "keep", "1")
    drop_a = TextType(metadata, "http://example.com/ns#", "ex", "drop", "a")
    drop_b = TextType(metadata, "http://example.com/ns#", "ex", "drop", "b")
    structured.add_property(keep)
    structured.add_property(drop_a)
    structured.add_property(drop_b)

    assert structured.has_property("drop") is True

    structured.clear_property("drop")

    assert structured.has_property("drop") is False
    assert structured.has_property("keep") is True
    assert structured.get_all_properties() == [keep]


def test_structured_type_clear_is_idempotent() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    structured = _Struct(metadata, property_name="container")
    structured.add_property(TextType(metadata, "http://example.com/ns#", "ex", "k", "v"))

    structured.clear()
    structured.clear()

    assert structured.get_all_properties() == []
    assert structured.has_property("k") is False

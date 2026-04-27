from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import ThumbnailType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    t = ThumbnailType(metadata)
    assert t.get_namespace() == "http://ns.adobe.com/xap/1.0/g/img/"
    assert t.get_prefix() == "xmpGImg"


def test_parse_type_attribute_set(metadata: XMPMetadata) -> None:
    t = ThumbnailType(metadata)
    attr = t.get_attribute("parseType")
    assert attr is not None
    assert attr.get_value() == "Resource"
    assert attr.get_namespace() == "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def test_initial_fields_none(metadata: XMPMetadata) -> None:
    t = ThumbnailType(metadata)
    assert t.get_height() is None
    assert t.get_width() is None
    assert t.get_image() is None
    assert t.get_format() is None


def test_set_and_get_dimensions(metadata: XMPMetadata) -> None:
    t = ThumbnailType(metadata)
    t.set_height(120)
    t.set_width(80)
    assert t.get_height() == 120
    assert t.get_width() == 80


def test_set_and_get_image_payload(metadata: XMPMetadata) -> None:
    t = ThumbnailType(metadata)
    t.set_image("base64payload==")
    assert t.get_image() == "base64payload=="


def test_set_and_get_format(metadata: XMPMetadata) -> None:
    t = ThumbnailType(metadata)
    t.set_format("JPEG")
    assert t.get_format() == "JPEG"


def test_field_constants() -> None:
    assert ThumbnailType.FORMAT == "format"
    assert ThumbnailType.HEIGHT == "height"
    assert ThumbnailType.WIDTH == "width"
    assert ThumbnailType.IMAGE == "image"

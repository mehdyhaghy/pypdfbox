from __future__ import annotations

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import FontType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix(metadata: XMPMetadata) -> None:
    f = FontType(metadata)
    assert f.get_namespace() == "http://ns.adobe.com/xap/1.0/sType/Font#"
    assert f.get_prefix() == "stFnt"


def test_field_constants() -> None:
    assert FontType.CHILD_FONT_FILES == "childFontFiles"
    assert FontType.COMPOSITE == "composite"
    assert FontType.FONT_FACE == "fontFace"
    assert FontType.FONT_FAMILY == "fontFamily"
    assert FontType.FONT_FILE_NAME == "fontFileName"
    assert FontType.FONT_NAME == "fontName"
    assert FontType.FONT_TYPE == "fontType"
    assert FontType.VERSION_STRING == "versionString"


def test_set_text_fields(metadata: XMPMetadata) -> None:
    f = FontType(metadata)
    f.add_simple_property(FontType.FONT_NAME, "Helvetica")
    f.add_simple_property(FontType.FONT_FAMILY, "Helvetica Family")
    f.add_simple_property(FontType.FONT_FACE, "Bold")
    f.add_simple_property(FontType.FONT_FILE_NAME, "helvetica.ttf")
    f.add_simple_property(FontType.VERSION_STRING, "1.0")
    assert f.get_property_value_as_string(FontType.FONT_NAME) == "Helvetica"
    assert f.get_property_value_as_string(FontType.FONT_FAMILY) == "Helvetica Family"
    assert f.get_property_value_as_string(FontType.FONT_FACE) == "Bold"
    assert f.get_property_value_as_string(FontType.FONT_FILE_NAME) == "helvetica.ttf"
    assert f.get_property_value_as_string(FontType.VERSION_STRING) == "1.0"


def test_set_composite_boolean(metadata: XMPMetadata) -> None:
    f = FontType(metadata)
    f.add_simple_property(FontType.COMPOSITE, True)
    assert f.get_property_value_as_string(FontType.COMPOSITE) == "True"
    f.add_simple_property(FontType.COMPOSITE, False)
    assert f.get_property_value_as_string(FontType.COMPOSITE) == "False"


def test_set_font_type_choice(metadata: XMPMetadata) -> None:
    f = FontType(metadata)
    f.add_simple_property(FontType.FONT_TYPE, "TrueType")
    assert f.get_property_value_as_string(FontType.FONT_TYPE) == "TrueType"

from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .boolean_type import BooleanType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class FontType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.FontType``. Represents the
    ``stFnt:Font`` XMP structure that records font information embedded in a
    document (``fontName`` / ``fontFamily`` / ``fontFace`` / ``composite`` /
    ``childFontFiles`` / ...).
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/sType/Font#"
    PREFERRED_PREFIX = "stFnt"

    CHILD_FONT_FILES = "childFontFiles"
    COMPOSITE = "composite"
    FONT_FACE = "fontFace"
    FONT_FAMILY = "fontFamily"
    FONT_FILE_NAME = "fontFileName"
    FONT_NAME = "fontName"
    FONT_TYPE = "fontType"
    VERSION_STRING = "versionString"

    _FIELD_TYPES = {
        CHILD_FONT_FILES: "Text",
        COMPOSITE: "Boolean",
        FONT_FACE: "Text",
        FONT_FAMILY: "Text",
        FONT_FILE_NAME: "Text",
        FONT_NAME: "Text",
        FONT_TYPE: "Choice",
        VERSION_STRING: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

    # --- childFontFiles ------------------------------------------------

    def get_child_font_files(self) -> str | None:
        return self.get_property_value_as_string(self.CHILD_FONT_FILES)

    def set_child_font_files(self, value: str) -> None:
        self.add_simple_property(self.CHILD_FONT_FILES, value)

    # --- composite (Boolean) -------------------------------------------

    def get_composite(self) -> bool | None:
        prop = self.get_first_equivalent_property(self.COMPOSITE, BooleanType)
        if isinstance(prop, BooleanType):
            return prop.get_value()
        return None

    def set_composite(self, value: bool) -> None:
        self.add_simple_property(self.COMPOSITE, value)

    # --- fontFace ------------------------------------------------------

    def get_font_face(self) -> str | None:
        return self.get_property_value_as_string(self.FONT_FACE)

    def set_font_face(self, value: str) -> None:
        self.add_simple_property(self.FONT_FACE, value)

    # --- fontFamily ----------------------------------------------------

    def get_font_family(self) -> str | None:
        return self.get_property_value_as_string(self.FONT_FAMILY)

    def set_font_family(self, value: str) -> None:
        self.add_simple_property(self.FONT_FAMILY, value)

    # --- fontFileName --------------------------------------------------

    def get_font_file_name(self) -> str | None:
        return self.get_property_value_as_string(self.FONT_FILE_NAME)

    def set_font_file_name(self, value: str) -> None:
        self.add_simple_property(self.FONT_FILE_NAME, value)

    # --- fontName ------------------------------------------------------

    def get_font_name(self) -> str | None:
        return self.get_property_value_as_string(self.FONT_NAME)

    def set_font_name(self, value: str) -> None:
        self.add_simple_property(self.FONT_NAME, value)

    # --- fontType (Choice) ---------------------------------------------

    def get_font_type(self) -> str | None:
        return self.get_property_value_as_string(self.FONT_TYPE)

    def set_font_type(self, value: str) -> None:
        self.add_simple_property(self.FONT_TYPE, value)

    # --- versionString -------------------------------------------------

    def get_version_string(self) -> str | None:
        return self.get_property_value_as_string(self.VERSION_STRING)

    def set_version_string(self, value: str) -> None:
        self.add_simple_property(self.VERSION_STRING, value)

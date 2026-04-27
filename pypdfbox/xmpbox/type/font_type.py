from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType

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

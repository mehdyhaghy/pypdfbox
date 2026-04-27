from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class ColorantType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.ColorantType``. Represents the
    ``xmpG:Colorant`` swatch structure used by XMP graphics packets — covers
    Lab, CMYK, and RGB component fields plus ``mode`` / ``swatchName`` /
    ``type`` metadata.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/g/"
    PREFERRED_PREFIX = "xmpG"

    A = "A"
    B = "B"
    L = "L"
    BLACK = "black"
    CYAN = "cyan"
    MAGENTA = "magenta"
    YELLOW = "yellow"
    BLUE = "blue"
    GREEN = "green"
    RED = "red"
    MODE = "mode"
    SWATCH_NAME = "swatchName"
    TYPE = "type"

    _FIELD_TYPES = {
        A: "Integer",
        B: "Integer",
        L: "Real",
        BLACK: "Real",
        CYAN: "Real",
        MAGENTA: "Real",
        YELLOW: "Real",
        BLUE: "Integer",
        GREEN: "Integer",
        RED: "Integer",
        MODE: "Choice",
        SWATCH_NAME: "Text",
        TYPE: "Choice",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

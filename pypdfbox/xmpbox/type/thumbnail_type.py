from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_field import Attribute
from .abstract_structured_type import AbstractStructuredType
from .choice_type import ChoiceType
from .integer_type import IntegerType
from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


_RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


class ThumbnailType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.ThumbnailType``. Represents the
    ``xmpGImg:Thumbnail`` structure used by XMP Basic to embed a small image
    preview (``format`` / ``width`` / ``height`` / ``image`` base64 payload).
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/g/img/"
    PREFERRED_PREFIX = "xmpGImg"

    FORMAT = "format"
    HEIGHT = "height"
    WIDTH = "width"
    IMAGE = "image"

    _FIELD_TYPES = {
        FORMAT: "Choice",
        HEIGHT: "Integer",
        WIDTH: "Integer",
        IMAGE: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)
        self.set_attribute(Attribute(_RDF_NAMESPACE, "parseType", "Resource"))

    def get_height(self) -> int | None:
        prop = self.get_first_equivalent_property(self.HEIGHT, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_height(self, value: int) -> None:
        self.add_simple_property(self.HEIGHT, value)

    def get_width(self) -> int | None:
        prop = self.get_first_equivalent_property(self.WIDTH, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_width(self, value: int) -> None:
        self.add_simple_property(self.WIDTH, value)

    def get_image(self) -> str | None:
        prop = self.get_first_equivalent_property(self.IMAGE, TextType)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def set_image(self, value: str) -> None:
        self.add_simple_property(self.IMAGE, value)

    def get_format(self) -> str | None:
        prop = self.get_first_equivalent_property(self.FORMAT, ChoiceType)
        if isinstance(prop, ChoiceType):
            return prop.get_string_value()
        return None

    def set_format(self, value: str) -> None:
        self.add_simple_property(self.FORMAT, value)

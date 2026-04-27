from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_field import Attribute
from .abstract_structured_type import AbstractStructuredType
from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


_RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


class LayerType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.LayerType``. Represents Photoshop's
    ``photoshop:Layer`` structure (``LayerName`` + ``LayerText``) used inside
    the ``photoshop:TextLayers`` Seq.
    """

    NAMESPACE = "http://ns.adobe.com/photoshop/1.0/"
    PREFERRED_PREFIX = "photoshop"

    LAYER_NAME = "LayerName"
    LAYER_TEXT = "LayerText"

    _FIELD_TYPES = {
        LAYER_NAME: "Text",
        LAYER_TEXT: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)
        self.set_attribute(Attribute(_RDF_NAMESPACE, "parseType", "Resource"))

    def get_layer_name(self) -> str | None:
        prop = self.get_first_equivalent_property(self.LAYER_NAME, TextType)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def set_layer_name(self, value: str) -> None:
        self.add_property(self.create_text_type(self.LAYER_NAME, value))

    def get_layer_text(self) -> str | None:
        prop = self.get_first_equivalent_property(self.LAYER_TEXT, TextType)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def set_layer_text(self, value: str) -> None:
        self.add_property(self.create_text_type(self.LAYER_TEXT, value))

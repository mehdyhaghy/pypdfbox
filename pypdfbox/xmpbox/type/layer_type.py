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
    layer structure carried inside the ``photoshop:TextLayers`` Seq.

    Upstream annotates the class with
    ``@StructuredType(preferedPrefix = "stLyr",
    namespace = "http://ns.adobe.com/photoshop/1.0/Layer#")``; the inner
    ``LayerName`` and ``LayerText`` fields therefore live under the
    ``http://ns.adobe.com/photoshop/1.0/Layer#`` namespace with the ``stLyr``
    prefix even though the enclosing ``photoshop:TextLayers`` Seq lives in the
    Photoshop schema namespace. This wave aligns the Python wrapper with the
    upstream annotation and adds typed accessors that go through the
    :class:`AbstractStructuredType` machinery (``add_simple_property`` /
    ``get_first_equivalent_property``) so the structured-type ``_FIELD_TYPES``
    registry drives wrapper construction the same way Dimensions / Job / Font
    types do.
    """

    NAMESPACE = "http://ns.adobe.com/photoshop/1.0/Layer#"
    PREFERRED_PREFIX = "stLyr"

    LAYER_NAME = "LayerName"
    LAYER_TEXT = "LayerText"

    _FIELD_TYPES = {
        LAYER_NAME: "Text",
        LAYER_TEXT: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)
        self.set_attribute(Attribute(_RDF_NAMESPACE, "parseType", "Resource"))

    # --- LayerName (Text) --------------------------------------------

    def get_layer_name(self) -> str | None:
        prop = self.get_first_equivalent_property(self.LAYER_NAME, TextType)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def set_layer_name(self, value: str) -> None:
        self.add_simple_property(self.LAYER_NAME, value)

    def get_layer_name_property(self) -> TextType | None:
        prop = self.get_first_equivalent_property(self.LAYER_NAME, TextType)
        return prop if isinstance(prop, TextType) else None

    def set_layer_name_property(self, value: TextType | None) -> None:
        if value is None:
            existing = self.get_property(self.LAYER_NAME)
            if existing is not None:
                self.remove_property(existing)
            return
        value.set_property_name(self.LAYER_NAME)
        self.add_property(value)

    # --- LayerText (Text) --------------------------------------------

    def get_layer_text(self) -> str | None:
        prop = self.get_first_equivalent_property(self.LAYER_TEXT, TextType)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def set_layer_text(self, value: str) -> None:
        self.add_simple_property(self.LAYER_TEXT, value)

    def get_layer_text_property(self) -> TextType | None:
        prop = self.get_first_equivalent_property(self.LAYER_TEXT, TextType)
        return prop if isinstance(prop, TextType) else None

    def set_layer_text_property(self, value: TextType | None) -> None:
        if value is None:
            existing = self.get_property(self.LAYER_TEXT)
            if existing is not None:
                self.remove_property(existing)
            return
        value.set_property_name(self.LAYER_TEXT)
        self.add_property(value)

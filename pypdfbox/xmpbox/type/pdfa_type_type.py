from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .array_property import ArrayProperty
from .text_type import TextType
from .uri_type import URIType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class PDFATypeType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.PDFATypeType``. Represents one
    entry of the ``pdfaSchema:valueType`` Seq inside the PDF/A Extension
    schema — the description of a custom value type contributed by a
    third-party schema (``type`` / ``namespaceURI`` / ``prefix`` /
    ``description`` / ``field`` Seq of :class:`PDFAFieldType`).
    """

    NAMESPACE = "http://www.aiim.org/pdfa/ns/type#"
    PREFERRED_PREFIX = "pdfaType"

    TYPE = "type"
    NS_URI = "namespaceURI"
    PREFIX = "prefix"
    DESCRIPTION = "description"
    FIELD = "field"

    _FIELD_TYPES = {
        TYPE: "Text",
        NS_URI: "URI",
        PREFIX: "Text",
        DESCRIPTION: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

    def get_namespace_uri(self) -> str | None:
        prop = self.get_property(self.NS_URI)
        if isinstance(prop, URIType):
            return prop.get_string_value()
        return None

    def get_type(self) -> str | None:
        prop = self.get_property(self.TYPE)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def get_prefix_value(self) -> str | None:
        prop = self.get_property(self.PREFIX)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def get_description(self) -> str | None:
        prop = self.get_property(self.DESCRIPTION)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def get_fields(self) -> ArrayProperty | None:
        return self.get_array_property(self.FIELD)

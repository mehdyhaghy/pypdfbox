from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .array_property import ArrayProperty, Cardinality
from .text_type import TextType
from .uri_type import URIType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata
    from .pdfa_property_type import PDFAPropertyType
    from .pdfa_type_type import PDFATypeType


class PDFASchemaType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.PDFASchemaType``. Represents one
    entry of the ``pdfaExtension:schemas`` Bag — a description of a
    third-party XMP schema embedded in a PDF/A document. Carries the
    human-readable schema name, namespace URI and prefix, plus optional
    ``property`` (Seq of :class:`PDFAPropertyType`) and ``valueType`` (Seq
    of :class:`PDFATypeType`) seqs describing the custom properties and
    value types contributed by the schema.
    """

    NAMESPACE = "http://www.aiim.org/pdfa/ns/schema#"
    PREFERRED_PREFIX = "pdfaSchema"

    SCHEMA = "schema"
    NAMESPACE_URI = "namespaceURI"
    PREFIX = "prefix"
    PROPERTY = "property"
    VALUE_TYPE = "valueType"

    _FIELD_TYPES = {
        SCHEMA: "Text",
        NAMESPACE_URI: "URI",
        PREFIX: "Text",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

    def get_namespace_uri(self) -> str | None:
        prop = self.get_property(self.NAMESPACE_URI)
        if isinstance(prop, URIType):
            return prop.get_string_value()
        return None

    def get_prefix_value(self) -> str | None:
        prop = self.get_property(self.PREFIX)
        if isinstance(prop, TextType):
            return prop.get_string_value()
        return None

    def get_property_array(self) -> ArrayProperty | None:
        # Upstream's ``getProperty()`` returns the ``property`` ArrayProperty
        # via Java overloading against the inherited ``getProperty(String)``.
        # Python can't overload by arity safely without breaking the parent's
        # field-name lookup, so the no-arg variant is renamed.
        return self.get_array_property(self.PROPERTY)

    def add_property_description(self, prop: PDFAPropertyType) -> None:
        array = self._get_or_create_seq(self.PROPERTY)
        array.add_property(prop)

    def get_property_descriptions(self) -> list[PDFAPropertyType]:
        from .pdfa_property_type import PDFAPropertyType

        array = self.get_property_array()
        if array is None:
            return []
        return [
            prop
            for prop in array.get_all_properties()
            if isinstance(prop, PDFAPropertyType)
        ]

    def get_value_type(self) -> ArrayProperty | None:
        return self.get_array_property(self.VALUE_TYPE)

    def add_value_type_description(self, value_type: PDFATypeType) -> None:
        array = self._get_or_create_seq(self.VALUE_TYPE)
        array.add_property(value_type)

    def get_value_type_descriptions(self) -> list[PDFATypeType]:
        from .pdfa_type_type import PDFATypeType

        array = self.get_value_type()
        if array is None:
            return []
        return [
            prop
            for prop in array.get_all_properties()
            if isinstance(prop, PDFATypeType)
        ]

    def _get_or_create_seq(self, property_name: str) -> ArrayProperty:
        array = self.get_array_property(property_name)
        if array is not None:
            return array
        array = self.create_array_property(property_name, Cardinality.Seq)
        self.add_property(array)
        return array

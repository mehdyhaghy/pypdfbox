from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .abstract_simple_property import AbstractSimpleProperty
from .agent_name_type import AgentNameType
from .array_property import ArrayProperty, Cardinality
from .boolean_type import BooleanType
from .choice_type import ChoiceType
from .colorant_type import ColorantType
from .date_type import DateType
from .dimensions_type import DimensionsType
from .font_type import FontType
from .guid_type import GUIDType
from .integer_type import IntegerType
from .job_type import JobType
from .lang_alt import LangAlt
from .layer_type import LayerType
from .mime_type import MIMEType
from .pdfa_field_description_type import PDFAFieldType
from .pdfa_property_type import PDFAPropertyType
from .pdfa_schema_type import PDFASchemaType
from .pdfa_type_type import PDFATypeType
from .proper_name_type import ProperNameType
from .rational_type import RationalType
from .real_type import RealType
from .rendition_class_type import RenditionClassType
from .resource_event_type import ResourceEventType
from .resource_ref_type import ResourceRefType
from .text_type import TextType
from .thumbnail_type import ThumbnailType
from .uri_type import URIType
from .url_type import URLType
from .version_type import VersionType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata
    from .abstract_structured_type import AbstractStructuredType


_SIMPLE_TYPE_REGISTRY: dict[str, type[AbstractSimpleProperty]] = {
    "Text": TextType,
    "Integer": IntegerType,
    "Boolean": BooleanType,
    "Date": DateType,
    "Real": RealType,
    "URI": URIType,
    "URL": URLType,
    "ProperName": ProperNameType,
    "AgentName": AgentNameType,
    "MIMEType": MIMEType,
    "RenditionClass": RenditionClassType,
    "GUID": GUIDType,
    "Choice": ChoiceType,
    "Rational": RationalType,
}


_STRUCTURED: dict[str, type] = {
    "Dimensions": DimensionsType,
    "Colorant": ColorantType,
    "Font": FontType,
    "ResourceRef": ResourceRefType,
    "ResourceEvent": ResourceEventType,
    "Version": VersionType,
    "Thumbnail": ThumbnailType,
    "Layer": LayerType,
    "Job": JobType,
    "PDFAField": PDFAFieldType,
    "PDFAProperty": PDFAPropertyType,
    "PDFASchema": PDFASchemaType,
    "PDFAType": PDFATypeType,
}


class TypeMapping:
    """
    Registry that instantiates typed XMP properties by short type name.

    Ported (subset) from ``org.apache.xmpbox.type.TypeMapping``. Upstream
    additionally maintains schema factories and per-property
    ``PropertiesDescription`` annotation maps keyed off Java reflection;
    this port keeps the type registry, the per-type ``createXxx`` helpers,
    and a structured-type lookup keyed by upstream type-name strings. Schema
    factories and the ``PropertiesDescription`` machinery land in a later
    wave when typed-property writes flow through the parser.
    """

    def __init__(self, metadata: XMPMetadata) -> None:
        self._metadata = metadata

    def get_metadata(self) -> XMPMetadata:
        return self._metadata

    def is_simple_type_known(self, type_name: str) -> bool:
        return type_name in _SIMPLE_TYPE_REGISTRY

    def is_structured_type_known(self, type_name: str) -> bool:
        return type_name in _STRUCTURED

    def is_structured_type_namespace(self, namespace: str) -> bool:
        return any(
            getattr(cls, "NAMESPACE", None) == namespace
            for cls in _STRUCTURED.values()
        )

    def instanciate_simple_property(
        self,
        ns_uri: str | None,
        prefix: str | None,
        name: str,
        value: object,
        type_name: str,
    ) -> AbstractSimpleProperty:
        cls = _SIMPLE_TYPE_REGISTRY.get(type_name)
        if cls is None:
            raise ValueError(f"Unknown simple property type: {type_name!r}")
        try:
            return cls(self._metadata, ns_uri, prefix, name, value)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Failed to instantiate {cls.__name__} property with value {value!r}"
            ) from exc

    def instanciate_structured_type(
        self, type_name: str, property_name: str | None = None
    ) -> AbstractStructuredType:
        cls = _STRUCTURED.get(type_name)
        if cls is None:
            raise ValueError(f"Unknown structured property type: {type_name!r}")
        instance = cls(self._metadata)
        if property_name is not None:
            instance.set_property_name(property_name)
        return instance

    def create_text(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> TextType:
        return TextType(self._metadata, ns_uri, prefix, name, value)

    def create_integer(
        self, ns_uri: str | None, prefix: str | None, name: str, value: int
    ) -> IntegerType:
        return IntegerType(self._metadata, ns_uri, prefix, name, value)

    def create_boolean(
        self, ns_uri: str | None, prefix: str | None, name: str, value: bool
    ) -> BooleanType:
        return BooleanType(self._metadata, ns_uri, prefix, name, value)

    def create_date(
        self, ns_uri: str | None, prefix: str | None, name: str, value: datetime
    ) -> DateType:
        return DateType(self._metadata, ns_uri, prefix, name, value)

    def create_real(
        self, ns_uri: str | None, prefix: str | None, name: str, value: float
    ) -> RealType:
        return RealType(self._metadata, ns_uri, prefix, name, value)

    def create_uri(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> URIType:
        return URIType(self._metadata, ns_uri, prefix, name, value)

    def create_url(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> URLType:
        return URLType(self._metadata, ns_uri, prefix, name, value)

    def create_rendition_class(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> RenditionClassType:
        return RenditionClassType(self._metadata, ns_uri, prefix, name, value)

    def create_proper_name(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> ProperNameType:
        return ProperNameType(self._metadata, ns_uri, prefix, name, value)

    def create_agent_name(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> AgentNameType:
        return AgentNameType(self._metadata, ns_uri, prefix, name, value)

    def create_mime_type(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> MIMEType:
        return MIMEType(self._metadata, ns_uri, prefix, name, value)

    def create_guid(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> GUIDType:
        return GUIDType(self._metadata, ns_uri, prefix, name, value)

    def create_choice(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> ChoiceType:
        return ChoiceType(self._metadata, ns_uri, prefix, name, value)

    def create_rational(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> RationalType:
        return RationalType(self._metadata, ns_uri, prefix, name, value)

    def create_array_property(
        self,
        ns_uri: str | None,
        prefix: str | None,
        name: str,
        cardinality: Cardinality,
    ) -> ArrayProperty:
        return ArrayProperty(self._metadata, ns_uri, prefix, name, cardinality)

    def create_lang_alt(
        self, ns_uri: str | None, prefix: str | None, name: str
    ) -> LangAlt:
        return LangAlt(self._metadata, ns_uri, prefix, name)

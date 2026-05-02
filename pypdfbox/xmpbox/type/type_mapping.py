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
from .locale_type import LocaleType
from .mime_type import MIMEType
from .part_type import PartType
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
from .xpath_type import XPathType

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
    "Locale": LocaleType,
    "XPath": XPathType,
    "Part": PartType,
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


# Namespace URIs of the built-in XMP schemas the upstream TypeMapping
# pre-registers via ``addNameSpace`` during initialization. Recorded here as
# string literals to avoid importing the schema classes (which would create a
# package-level import cycle) — they are stable parts of the XMP standard.
_BUILTIN_SCHEMA_NAMESPACES: frozenset[str] = frozenset(
    {
        "http://ns.adobe.com/xap/1.0/",  # XMP Basic
        "http://purl.org/dc/elements/1.1/",  # Dublin Core
        "http://www.aiim.org/pdfa/ns/extension/",  # PDF/A Extension
        "http://ns.adobe.com/xap/1.0/mm/",  # XMP Media Management
        "http://ns.adobe.com/pdf/1.3/",  # Adobe PDF
        "http://www.aiim.org/pdfa/ns/id/",  # PDF/A Identification
        "http://ns.adobe.com/xap/1.0/rights/",  # XMP Rights Management
        "http://ns.adobe.com/photoshop/1.0/",  # Photoshop
        "http://ns.adobe.com/xap/1.0/bj/",  # XMP Basic Job Ticket
        "http://ns.adobe.com/exif/1.0/",  # Exif
        "http://ns.adobe.com/tiff/1.0/",  # TIFF
        "http://ns.adobe.com/xap/1.0/t/pg/",  # XMP Paged Text
    }
)


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
        # ns -> typeName for namespaces registered via
        # ``add_to_defined_structured_types`` (mirrors upstream
        # ``definedStructuredNamespaces``).
        self._defined_structured_namespaces: dict[str, str] = {}
        # typeName -> ns lookup populated alongside the namespace map so that
        # ``is_defined_type`` is a constant-time membership check.
        self._defined_structured_types: dict[str, str] = {}
        # Namespaces registered through ``add_new_namespace`` (deferred-schema
        # equivalent of upstream ``schemaMap`` entries created via
        # ``addNewNameSpace``).
        self._defined_namespaces: dict[str, str | None] = {}

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

    def is_defined_schema(self, namespace: str) -> bool:
        """
        Return ``True`` for any of the built-in XMP schema namespaces upstream
        pre-registers (Dublin Core, XMP Basic, Photoshop, TIFF, Exif, ...) plus
        any namespace added via :meth:`add_new_namespace`.
        """
        return (
            namespace in _BUILTIN_SCHEMA_NAMESPACES
            or namespace in self._defined_namespaces
        )

    def is_defined_type(self, name: str) -> bool:
        """Return ``True`` if ``name`` was registered via
        :meth:`add_to_defined_structured_types`."""
        return name in self._defined_structured_types

    def is_defined_type_namespace(self, namespace: str) -> bool:
        """Return ``True`` if ``namespace`` was registered via
        :meth:`add_to_defined_structured_types`."""
        return namespace in self._defined_structured_namespaces

    def is_defined_namespace(self, namespace: str) -> bool:
        """Composite check covering every namespace TypeMapping knows about:
        a built-in/registered schema, a namespace owned by a built-in
        structured type, or a defined-type namespace."""
        return (
            self.is_defined_schema(namespace)
            or self.is_structured_type_namespace(namespace)
            or self.is_defined_type_namespace(namespace)
        )

    def add_new_namespace(
        self, namespace: str, preferred_prefix: str | None = None
    ) -> None:
        """Register an extra schema namespace (mirror of upstream
        ``addNewNameSpace``). The preferred prefix is recorded for callers
        that want to resolve it later; upstream stashes it on the schema
        factory which we do not yet wire."""
        self._defined_namespaces[namespace] = preferred_prefix

    def add_to_defined_structured_types(
        self, type_name: str, namespace: str
    ) -> None:
        """Register a structured type that was *defined* (rather than built
        in). Mirror of upstream ``addToDefinedStructuredTypes`` minus the
        ``PropertiesDescription`` argument, which depends on the
        reflection-based annotation machinery deferred to a later wave."""
        self._defined_structured_namespaces[namespace] = type_name
        self._defined_structured_types[type_name] = namespace

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

    def create_locale(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> LocaleType:
        return LocaleType(self._metadata, ns_uri, prefix, name, value)

    def create_xpath(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> XPathType:
        return XPathType(self._metadata, ns_uri, prefix, name, value)

    def create_part(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> PartType:
        return PartType(self._metadata, ns_uri, prefix, name, value)

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

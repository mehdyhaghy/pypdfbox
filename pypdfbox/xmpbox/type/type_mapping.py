from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from .abstract_simple_property import AbstractSimpleProperty
from .abstract_structured_type import AbstractStructuredType
from .agent_name_type import AgentNameType
from .array_property import ArrayProperty, Cardinality
from .boolean_type import BooleanType
from .choice_type import ChoiceType
from .colorant_type import ColorantType
from .date_type import DateType
from .dimensions_type import DimensionsType
from .font_type import FontType
from .gps_coordinate_type import GPSCoordinateType
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
    "GPSCoordinate": GPSCoordinateType,
    "Locale": LocaleType,
    "XPath": XPathType,
    "Part": PartType,
}


_STRUCTURED: dict[str, type[AbstractStructuredType]] = {
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


@dataclass(frozen=True)
class PropertyType:
    """Mirror of upstream ``org.apache.xmpbox.type.PropertyType``.

    Upstream is a Java annotation describing the type and cardinality of a
    schema property. Here it is a small immutable record carrying the
    declared simple-type name (``Text`` / ``Integer`` / ``Real`` / ...) and
    the :class:`Cardinality` (``Simple`` / ``Bag`` / ``Seq`` / ``Alt``).
    """

    type: str
    card: Cardinality = Cardinality.Simple

    def __str__(self) -> str:
        # Mirrors upstream anonymous-implementation ``toString()`` (line 555).
        return f"{{type: {self.type}, card: {self.card.name}}}"


class PropertiesDescription:
    """Mirror of upstream ``org.apache.xmpbox.type.PropertiesDescription``.

    Maps a property local-name to its declared :class:`PropertyType`. Used
    by :class:`TypeMapping` to record the declared properties of a schema
    or a defined structured type.
    """

    def __init__(self) -> None:
        self._types: dict[str, PropertyType] = {}

    def get_properties_names(self) -> list[str]:
        """All known property names (upstream ``getPropertiesNames``)."""
        return list(self._types.keys())

    def get_properties_name(self) -> list[str]:
        """Deprecated upstream alias for :meth:`get_properties_names`."""
        return self.get_properties_names()

    def add_new_property(self, name: str, type_: PropertyType) -> None:
        """Register ``name`` as a property of the given :class:`PropertyType`."""
        self._types[name] = type_

    def get_property_type(self, name: str) -> PropertyType | None:
        """Return the :class:`PropertyType` for ``name`` or ``None``."""
        return self._types.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self._types

    def __repr__(self) -> str:
        return f"PropertiesDescription{{types={self._types}}}"


class DefinedStructuredType(AbstractStructuredType):
    """Mirror of upstream ``org.apache.xmpbox.type.DefinedStructuredType``.

    Lightweight structured type used as a fallback when the TypeMapping is
    asked to instantiate a structured value for a namespace that was
    *defined* (via ``add_to_defined_structured_types``) rather than
    statically known. Carries a private ``definedProperties`` map so the
    parser can attach its discovered properties.
    """

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None = None,
        field_prefix: str | None = None,
        property_name: str | None = None,
    ) -> None:
        super().__init__(metadata, namespace_uri, field_prefix, property_name)
        self._defined_properties: dict[str, PropertyType] = {}

    def add_property_definition(self, name: str, type_: PropertyType) -> None:
        """Register a property declaration on this defined-type instance."""
        self._defined_properties[name] = type_

    def get_defined_properties(self) -> dict[str, PropertyType]:
        """Return the declared-properties map (upstream ``getDefinedProperties``)."""
        return self._defined_properties

class _SchemaFactory:
    """Lightweight schema-factory record.

    Upstream ``XMPSchemaFactory`` couples a namespace, a ``XMPSchema``
    subclass, and the schema's :class:`PropertiesDescription`. Schema-class
    construction is not used by the parser-side wiring TypeMapping needs
    today, so this implementation only carries the namespace plus the
    ``PropertiesDescription`` lookup. The interface mirrors the subset
    upstream ``getSpecifiedPropertyType`` actually consumes
    (``getPropertyType``).
    """

    def __init__(
        self, namespace: str, properties: PropertiesDescription | None = None
    ) -> None:
        self._namespace = namespace
        self._properties = properties or PropertiesDescription()

    def get_namespace(self) -> str:
        return self._namespace

    def get_property_type(self, property_name: str) -> PropertyType | None:
        return self._properties.get_property_type(property_name)

    def get_properties_description(self) -> PropertiesDescription:
        return self._properties


# Type-name strings that ``createPropertyType`` may return for structured
# values. ``DefinedType`` is a sentinel name upstream's ``Types`` enum uses
# for any structured value reached through a *defined* (extension) namespace.
DEFINED_TYPE = "DefinedType"


class TypeMapping:
    """
    Registry that instantiates typed XMP properties by short type name.

    Ported from ``org.apache.xmpbox.type.TypeMapping``. Wave 1239 brought
    the missing PropertyType / PropertiesDescription / DefinedStructuredType
    plumbing plus the schema-factory lookup so the DOM parser can route
    structured / defined types through this class. The schema-factory side
    keeps a minimal surface (namespace + properties description) — schema
    *instantiation* is owned by the schemas themselves and is not needed by
    the parser-side path TypeMapping is asked to support.
    """

    def __init__(self, metadata: XMPMetadata) -> None:
        self._metadata = metadata
        # ns -> typeName for namespaces registered via
        # ``add_to_defined_structured_types`` (mirrors upstream
        # ``definedStructuredNamespaces``, the deprecated single-name map).
        self._defined_structured_namespaces: dict[str, str] = {}
        # typeName -> ns lookup populated alongside the namespace map so that
        # ``is_defined_type`` is a constant-time membership check.
        self._defined_structured_types: dict[str, str] = {}
        # ns -> list of PropertiesDescription (mirrors upstream
        # ``definedStructuredNamespaces2``). Several defined types may live
        # under the same namespace; ``getDefinedDescriptionByNamespace``
        # disambiguates by inspecting the field name.
        self._defined_structured_namespaces2: dict[
            str, list[PropertiesDescription]
        ] = {}
        # typeName -> PropertiesDescription (upstream ``definedStructuredMappings``).
        self._defined_structured_mappings: dict[str, PropertiesDescription] = {}
        # Namespaces registered through ``add_new_namespace`` (deferred-schema
        # equivalent of upstream ``schemaMap`` entries created via
        # ``addNewNameSpace``).
        self._defined_namespaces: dict[str, str | None] = {}
        # typeName -> PropertiesDescription for built-in structured types
        # (mirrors upstream ``structuredMappings``). Populated from each
        # structured type's class-level ``_FIELD_TYPES`` map so the parser
        # can ask whether a candidate field name belongs to a given struct.
        self._structured_mappings: dict[str, PropertiesDescription] = {
            type_name: _properties_description_from_field_types(cls)
            for type_name, cls in _STRUCTURED.items()
        }
        # ns -> list[typeName] for every structured type whose NAMESPACE
        # matches (upstream ``structuredNamespaces2``). Computed once at
        # construction since the registry is immutable.
        self._structured_namespaces2: dict[str, list[str]] = {}
        for type_name, cls in _STRUCTURED.items():
            ns = getattr(cls, "NAMESPACE", None)
            if ns is None:
                continue
            self._structured_namespaces2.setdefault(ns, []).append(type_name)
        # ns -> _SchemaFactory (upstream ``schemaMap``). Populated lazily
        # for namespaces added via ``add_new_namespace``.
        self._schema_factories: dict[str, _SchemaFactory] = {}

    # --- accessors ----------------------------------------------------

    def get_metadata(self) -> XMPMetadata:
        return self._metadata

    def is_simple_type_known(self, type_name: str) -> bool:
        return type_name in _SIMPLE_TYPE_REGISTRY

    def is_structured_type_known(self, type_name: str) -> bool:
        return type_name in _STRUCTURED

    def is_structured_type_namespace(self, namespace: str) -> bool:
        return namespace in self._structured_namespaces2

    def is_defined_schema(self, namespace: str) -> bool:
        """
        Return ``True`` for any of the built-in XMP schema namespaces upstream
        pre-registers (Dublin Core, XMP Basic, Photoshop, TIFF, Exif, ...) plus
        any namespace added via :meth:`add_new_namespace`.
        """
        return (
            namespace in _BUILTIN_SCHEMA_NAMESPACES
            or namespace in self._defined_namespaces
            or namespace in self._schema_factories
        )

    def is_defined_type(self, name: str) -> bool:
        """Return ``True`` if ``name`` was registered via
        :meth:`add_to_defined_structured_types`."""
        return name in self._defined_structured_types

    def is_defined_type_namespace(self, namespace: str) -> bool:
        """Return ``True`` if ``namespace`` was registered via
        :meth:`add_to_defined_structured_types`."""
        return namespace in self._defined_structured_namespaces2

    def is_defined_namespace(self, namespace: str) -> bool:
        """Composite check covering every namespace TypeMapping knows about:
        a built-in/registered schema, a namespace owned by a built-in
        structured type, or a defined-type namespace."""
        return (
            self.is_defined_schema(namespace)
            or self.is_structured_type_namespace(namespace)
            or self.is_defined_type_namespace(namespace)
        )

    # --- registration -------------------------------------------------

    def add_new_namespace(
        self, namespace: str, preferred_prefix: str | None = None
    ) -> None:
        """Register an extra schema namespace (upstream ``addNewNameSpace``).
        Creates an empty :class:`PropertiesDescription` so subsequent property
        lookups have a backing factory entry."""
        self._defined_namespaces[namespace] = preferred_prefix
        if namespace not in self._schema_factories:
            self._schema_factories[namespace] = _SchemaFactory(
                namespace, PropertiesDescription()
            )

    def add_to_defined_structured_types(
        self,
        type_name: str,
        namespace: str,
        properties: PropertiesDescription | None = None,
    ) -> None:
        """Register a structured type that was *defined* (upstream
        ``addToDefinedStructuredTypes``). The optional ``properties``
        argument lets callers carry the discovered field declarations
        forward; when omitted an empty :class:`PropertiesDescription` is
        stored so :meth:`get_defined_description_by_namespace` returns a
        non-``None`` placeholder."""
        if properties is None:
            properties = PropertiesDescription()
        # Upstream maintains both the deprecated single-name map and the
        # multi-PropertiesDescription list keyed by namespace; mirror both.
        self._defined_structured_namespaces[namespace] = type_name
        self._defined_structured_types[type_name] = namespace
        self._defined_structured_mappings[type_name] = properties
        self._defined_structured_namespaces2.setdefault(namespace, []).append(
            properties
        )

    # --- defined-type lookups ----------------------------------------

    def get_defined_description_by_namespace(
        self, namespace: str, pdfa_field_name: str | None = None
    ) -> PropertiesDescription | None:
        """Return the :class:`PropertiesDescription` registered for
        ``namespace``.

        When ``pdfa_field_name`` is supplied, scan the per-namespace list for
        the description whose declared property names contain it (mirror of
        upstream two-arg ``getDefinedDescriptionByNamespace`` at line 176).
        Otherwise behaves like the deprecated single-arg upstream variant.
        """
        if pdfa_field_name is None:
            type_name = self._defined_structured_namespaces.get(namespace)
            if type_name is None:
                return None
            return self._defined_structured_mappings.get(type_name)
        descriptions = self._defined_structured_namespaces2.get(namespace)
        if descriptions is None:
            return None
        for desc in descriptions:
            if pdfa_field_name in desc.get_properties_names():
                return desc
        return None

    # --- structured / schema lookups ---------------------------------

    def get_structured_prop_mapping(self, type_name: str) -> PropertiesDescription | None:
        """Return the :class:`PropertiesDescription` for a built-in structured
        type (upstream ``getStructuredPropMapping`` at line 280)."""
        return self._structured_mappings.get(type_name)

    def get_schema_factory(self, namespace: str) -> _SchemaFactory | None:
        """Return the schema factory registered for ``namespace`` or ``None``
        (upstream ``getSchemaFactory`` at line 316)."""
        return self._schema_factories.get(namespace)

    def get_specified_property_type(
        self,
        qname: tuple[str, str],
        parent_type_name: str | None = None,
    ) -> PropertyType | None:
        """Resolve the :class:`PropertyType` declared for ``qname``.

        ``qname`` is a ``(namespace_uri, local_part)`` pair (upstream uses
        ``javax.xml.namespace.QName``). ``parent_type_name`` disambiguates
        when a namespace hosts several structured types that share field
        names (PDFBOX-6133 fix at upstream line 353).

        Raises ``BadFieldValueException`` (re-imported from
        :mod:`pypdfbox.xmpbox.pdfa_identification_schema`) when the
        namespace is unknown and not represented by a schema factory.
        """
        namespace_uri, local_part = qname
        # Schema lookup first.
        factory = self.get_schema_factory(namespace_uri)
        if factory is not None:
            prop_type = factory.get_property_type(local_part)
            if prop_type is not None:
                return prop_type
        # Built-in structured types.
        struct_list = self._structured_namespaces2.get(namespace_uri)
        if struct_list is not None:
            if len(struct_list) == 1:
                type_name = struct_list[0]
                desc = self._structured_mappings[type_name]
                if factory is None or local_part in desc.get_properties_names():
                    return create_property_type(type_name, Cardinality.Simple)
                return None
            for type_name in struct_list:
                if type_name == parent_type_name:
                    return create_property_type(type_name, Cardinality.Simple)
            for type_name in struct_list:
                desc = self._structured_mappings[type_name]
                if local_part in desc.get_properties_names():
                    return create_property_type(type_name, Cardinality.Simple)
            return None
        # Defined types.
        if namespace_uri not in self._defined_structured_namespaces2:
            if factory is not None:
                return None
            from ..pdfa_identification_schema import BadFieldValueException

            raise BadFieldValueException(
                f"No descriptor found for ({namespace_uri}, {local_part})"
            )
        return create_property_type(DEFINED_TYPE, Cardinality.Simple)

    # --- prop-mapping initialisation ---------------------------------

    @staticmethod
    def initialize_prop_mapping(cls: type) -> PropertiesDescription:
        """Build a :class:`PropertiesDescription` for ``cls``.

        Upstream walks the schema/struct class via reflection, picking up
        every public ``static final String`` field annotated with
        ``@PropertyType``. The Python port uses two pieces of metadata that
        already exist on our schema/struct classes:

        * ``_FIELD_TYPES`` (structured types): ``{field_name: type_name}``.
          Cardinality defaults to :attr:`Cardinality.Simple`.
        * ``PROPERTIES`` (schemas, optional): ``{field_name: PropertyType}``
          giving full type + cardinality declarations.

        Whichever is present is harvested; if both exist they are merged
        with ``PROPERTIES`` taking precedence.
        """
        desc = PropertiesDescription()
        field_types = getattr(cls, "_FIELD_TYPES", None)
        if isinstance(field_types, dict):
            for name, type_name in field_types.items():
                desc.add_new_property(
                    name, PropertyType(type=type_name, card=Cardinality.Simple)
                )
        explicit = getattr(cls, "PROPERTIES", None)
        if isinstance(explicit, dict):
            for name, declaration in explicit.items():
                if isinstance(declaration, PropertyType):
                    desc.add_new_property(name, declaration)
                elif isinstance(declaration, tuple) and len(declaration) == 2:
                    type_name, card = declaration
                    desc.add_new_property(
                        name, PropertyType(type=type_name, card=card)
                    )
        return desc

    # --- factory helpers ---------------------------------------------

    @staticmethod
    def create_property_type(
        type_name: str, cardinality: Cardinality = Cardinality.Simple
    ) -> PropertyType:
        """Build a :class:`PropertyType` record (upstream
        ``createPropertyType`` at line 529 returns an inline anonymous
        annotation; here it is just a constructor call)."""
        return PropertyType(type=type_name, card=cardinality)

    # --- instantiation -----------------------------------------------

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

    def instanciate_simple_field(
        self,
        cls: type,
        ns_uri: str | None,
        prefix: str | None,
        property_name: str,
        value: object,
    ) -> AbstractSimpleProperty:
        """Resolve ``property_name`` on ``cls`` to a :class:`PropertyType` and
        instantiate the matching simple property (upstream
        ``instanciateSimpleField`` at line 236)."""
        pm = TypeMapping.initialize_prop_mapping(cls)
        prop_type = pm.get_property_type(property_name)
        if prop_type is None:
            raise ValueError(
                f"{cls.__name__} has no PropertyType declaration for "
                f"{property_name!r}"
            )
        return self.instanciate_simple_property(
            ns_uri, prefix, property_name, value, prop_type.type
        )

    def instanciate_structured_type(
        self, type_name: str, property_name: str | None = None
    ) -> AbstractStructuredType:
        cls = _STRUCTURED.get(type_name)
        if cls is None:
            # Keep the historical pypdfbox message ("Unknown structured
            # property type") so existing call-site tests still match while
            # raising upstream's BadFieldValueException type. The Java
            # message is included as a parenthetical for parity with
            # upstream's ``instanciateStructuredType`` error text.
            from ..pdfa_identification_schema import BadFieldValueException

            raise BadFieldValueException(
                f"Unknown structured property type: {type_name!r} "
                f"(failed to instantiate structured type : {type_name})"
            )
        instance = cls(self._metadata)
        if property_name is not None:
            instance.set_property_name(property_name)
        return instance

    def instanciate_defined_type(
        self, property_name: str, namespace: str
    ) -> DefinedStructuredType:
        """Instantiate a :class:`DefinedStructuredType` for an extension
        namespace (upstream ``instanciateDefinedType`` at line 210)."""
        return DefinedStructuredType(
            self._metadata, namespace, None, property_name
        )

    # --- per-type create helpers -------------------------------------

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

    def create_gps_coordinate(
        self, ns_uri: str | None, prefix: str | None, name: str, value: str
    ) -> GPSCoordinateType:
        return GPSCoordinateType(self._metadata, ns_uri, prefix, name, value)

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


# Module-level alias to mirror upstream's public ``createPropertyType``
# (it is a static helper on ``TypeMapping`` upstream too — re-exported here
# so callers can use it without first instantiating a TypeMapping).
create_property_type = TypeMapping.create_property_type


def _properties_description_from_field_types(
    cls: type,
) -> PropertiesDescription:
    """Build a :class:`PropertiesDescription` from a structured type's
    ``_FIELD_TYPES`` map. Kept as a module-private helper so the
    eager-built ``_structured_mappings`` table on :class:`TypeMapping`
    stays a single comprehension."""
    desc = PropertiesDescription()
    field_types: dict[str, str] = getattr(cls, "_FIELD_TYPES", {}) or {}
    for name, type_name in field_types.items():
        desc.add_new_property(
            name, PropertyType(type=type_name, card=Cardinality.Simple)
        )
    return desc



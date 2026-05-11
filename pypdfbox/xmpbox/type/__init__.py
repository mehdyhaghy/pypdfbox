"""
pypdfbox.xmpbox.type — typed XMP property hierarchy.

Ported from ``org.apache.xmpbox.type``. Wave 31 landed the foundation
of the AbstractField / AbstractSimpleProperty hierarchy along with the
common simple-property wrappers (Text, Integer, Boolean, Date, Real, URI,
ProperName, AgentName, MIME, GUID, Choice), the array container
(ArrayProperty for Bag/Seq/Alt), the LangAlt convenience helper, and a
TypeMapping registry for instantiating typed wrappers by name. Wave 32
adds the structured-type foundation (``AbstractStructuredType``) and the
core structured types: Rational, Dimensions, Colorant, Font, ResourceRef,
ResourceEvent, Thumbnail, Layer, Job. Schemas continue to expose their
existing string-form accessors; migrating those callers to typed
properties is intentionally a separate wave so existing parser/serialiser
behavior is unaffected.
"""

from __future__ import annotations

from .abstract_complex_property import AbstractComplexProperty
from .abstract_field import AbstractField, Attribute
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
from .pdfa_field_description_type import PDFAFieldDescriptionType, PDFAFieldType
from .pdfa_property_type import PDFAPropertyType
from .pdfa_schema_type import PDFASchemaType
from .pdfa_type_type import PDFATypeType
from .pdfa_value_type_description_type import PDFAValueTypeDescriptionType
from .proper_name_type import ProperNameType
from .rational_type import RationalType
from .real_type import RealType
from .rendition_class_type import RenditionClassType
from .resource_event_type import ResourceEventType
from .resource_ref_type import ResourceRefType
from .complex_property_container import ComplexPropertyContainer
from .text_type import TextType
from .thumbnail_type import ThumbnailType
from .type_mapping import TypeMapping
from .types import Types
from .uri_type import URIType
from .url_type import URLType
from .version_type import VersionType
from .xpath_type import XPathType

__all__ = [
    "AbstractComplexProperty",
    "AbstractField",
    "AbstractSimpleProperty",
    "AbstractStructuredType",
    "AgentNameType",
    "ArrayProperty",
    "Attribute",
    "BooleanType",
    "Cardinality",
    "ChoiceType",
    "ColorantType",
    "ComplexPropertyContainer",
    "DateType",
    "DimensionsType",
    "FontType",
    "GPSCoordinateType",
    "GUIDType",
    "IntegerType",
    "JobType",
    "LangAlt",
    "LayerType",
    "LocaleType",
    "MIMEType",
    "PartType",
    "PDFAFieldDescriptionType",
    "PDFAFieldType",
    "PDFAPropertyType",
    "PDFASchemaType",
    "PDFATypeType",
    "PDFAValueTypeDescriptionType",
    "ProperNameType",
    "RationalType",
    "RealType",
    "RenditionClassType",
    "ResourceEventType",
    "ResourceRefType",
    "TextType",
    "ThumbnailType",
    "TypeMapping",
    "Types",
    "URIType",
    "URLType",
    "VersionType",
    "XPathType",
]

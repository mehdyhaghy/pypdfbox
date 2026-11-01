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

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .abstract_complex_property import AbstractComplexProperty
    from .abstract_field import (
        AbstractField,
        Attribute,
    )
    from .abstract_simple_property import AbstractSimpleProperty
    from .abstract_structured_type import AbstractStructuredType
    from .agent_name_type import AgentNameType
    from .array_property import (
        ArrayProperty,
        Cardinality,
    )
    from .boolean_type import BooleanType
    from .cfa_pattern_type import CFAPatternType
    from .choice_type import ChoiceType
    from .colorant_type import ColorantType
    from .complex_property_container import ComplexPropertyContainer
    from .date_type import DateType
    from .device_settings_type import DeviceSettingsType
    from .dimensions_type import DimensionsType
    from .flash_type import FlashType
    from .font_type import FontType
    from .gps_coordinate_type import GPSCoordinateType
    from .guid_type import GUIDType
    from .integer_type import IntegerType
    from .job_type import JobType
    from .lang_alt import LangAlt
    from .layer_type import LayerType
    from .locale_type import LocaleType
    from .mime_type import MIMEType
    from .oecf_type import OECFType
    from .part_type import PartType
    from .pdfa_field_description_type import (
        PDFAFieldDescriptionType,
        PDFAFieldType,
    )
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
    from .text_type import TextType
    from .thumbnail_type import ThumbnailType
    from .type_mapping import TypeMapping
    from .types import Types
    from .uri_type import URIType
    from .url_type import URLType
    from .version_type import VersionType
    from .xpath_type import XPathType

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AbstractComplexProperty": ".abstract_complex_property",
        "AbstractField": ".abstract_field",
        "Attribute": ".abstract_field",
        "AbstractSimpleProperty": ".abstract_simple_property",
        "AbstractStructuredType": ".abstract_structured_type",
        "AgentNameType": ".agent_name_type",
        "ArrayProperty": ".array_property",
        "Cardinality": ".array_property",
        "BooleanType": ".boolean_type",
        "CFAPatternType": ".cfa_pattern_type",
        "ChoiceType": ".choice_type",
        "ColorantType": ".colorant_type",
        "ComplexPropertyContainer": ".complex_property_container",
        "DateType": ".date_type",
        "DeviceSettingsType": ".device_settings_type",
        "DimensionsType": ".dimensions_type",
        "FlashType": ".flash_type",
        "FontType": ".font_type",
        "GPSCoordinateType": ".gps_coordinate_type",
        "GUIDType": ".guid_type",
        "IntegerType": ".integer_type",
        "JobType": ".job_type",
        "LangAlt": ".lang_alt",
        "LayerType": ".layer_type",
        "LocaleType": ".locale_type",
        "MIMEType": ".mime_type",
        "OECFType": ".oecf_type",
        "PartType": ".part_type",
        "PDFAFieldDescriptionType": ".pdfa_field_description_type",
        "PDFAFieldType": ".pdfa_field_description_type",
        "PDFAPropertyType": ".pdfa_property_type",
        "PDFASchemaType": ".pdfa_schema_type",
        "PDFATypeType": ".pdfa_type_type",
        "PDFAValueTypeDescriptionType": ".pdfa_value_type_description_type",
        "ProperNameType": ".proper_name_type",
        "RationalType": ".rational_type",
        "RealType": ".real_type",
        "RenditionClassType": ".rendition_class_type",
        "ResourceEventType": ".resource_event_type",
        "ResourceRefType": ".resource_ref_type",
        "TextType": ".text_type",
        "ThumbnailType": ".thumbnail_type",
        "TypeMapping": ".type_mapping",
        "Types": ".types",
        "URIType": ".uri_type",
        "URLType": ".url_type",
        "VersionType": ".version_type",
        "XPathType": ".xpath_type",
    },
)

__all__ = [
    "AbstractComplexProperty",
    "AbstractField",
    "AbstractSimpleProperty",
    "AbstractStructuredType",
    "AgentNameType",
    "ArrayProperty",
    "Attribute",
    "BooleanType",
    "CFAPatternType",
    "Cardinality",
    "ChoiceType",
    "ColorantType",
    "ComplexPropertyContainer",
    "DateType",
    "DeviceSettingsType",
    "DimensionsType",
    "FlashType",
    "FontType",
    "GPSCoordinateType",
    "GUIDType",
    "IntegerType",
    "JobType",
    "LangAlt",
    "LayerType",
    "LocaleType",
    "MIMEType",
    "OECFType",
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

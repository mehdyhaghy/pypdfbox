"""
pypdfbox.xmpbox — Python port of the Apache PDFBox xmpbox subproject.

Cluster #1 shipped the XMP packet read path: ``XMPMetadata`` plus a
``DomXmpParser`` backed by ``xml.etree.ElementTree``. Schema dispatch covers
the common Adobe, Dublin Core, PDF/A, PDF/UA, Photoshop, TIFF, and XMP
namespaces; unknown namespaces fall back to a plain :class:`XMPSchema`. Later
waves add the typed property hierarchy, ``ArrayProperty`` Bag/Seq/Alt
containers, ``TypeMapping``, and selected typed schema accessors while keeping
parser storage backwards-compatible.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .adobe_pdf_schema import AdobePDFSchema
    from .date_converter import DateConverter
    from .dom_xmp_parser import (
        DomXmpParser,
        XmpParsingException,
    )
    from .dublin_core_schema import DublinCoreSchema
    from .exif_schema import ExifSchema
    from .pdfa_extension_schema import PDFAExtensionSchema
    from .pdfa_identification_schema import (
        BadFieldValueException,
        PDFAIdentificationSchema,
    )
    from .pdfua_identification_schema import PDFUAIdentificationSchema
    from .photoshop_schema import PhotoshopSchema
    from .schema.xmp_page_text_schema import XMPPageTextSchema
    from .tiff_schema import TiffSchema
    from .type import (
        AbstractField,
        AbstractSimpleProperty,
        AbstractStructuredType,
        AgentNameType,
        ArrayProperty,
        Attribute,
        BooleanType,
        Cardinality,
        CFAPatternType,
        ChoiceType,
        ColorantType,
        DateType,
        DimensionsType,
        FontType,
        GPSCoordinateType,
        GUIDType,
        IntegerType,
        LangAlt,
        LayerType,
        LocaleType,
        MIMEType,
        OECFType,
        PartType,
        ProperNameType,
        RationalType,
        RealType,
        RenditionClassType,
        ResourceEventType,
        ResourceRefType,
        TextType,
        ThumbnailType,
        TypeMapping,
        URIType,
        URLType,
        VersionType,
        XPathType,
    )
    from .xml.xmp_serialization_exception import XmpSerializationException
    from .xmp_basic_job_ticket_schema import (
        JobType,
        XMPBasicJobTicketSchema,
    )
    from .xmp_basic_schema import XMPBasicSchema
    from .xmp_constants import XmpConstants
    from .xmp_media_management_schema import XMPMediaManagementSchema
    from .xmp_metadata import XMPMetadata
    from .xmp_paged_text_schema import XMPageTextSchema
    from .xmp_rights_management_schema import XMPRightsManagementSchema
    from .xmp_schema import XMPSchema

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AdobePDFSchema": ".adobe_pdf_schema",
        "DateConverter": ".date_converter",
        "DomXmpParser": ".dom_xmp_parser",
        "XmpParsingException": ".dom_xmp_parser",
        "DublinCoreSchema": ".dublin_core_schema",
        "ExifSchema": ".exif_schema",
        "PDFAExtensionSchema": ".pdfa_extension_schema",
        "BadFieldValueException": ".pdfa_identification_schema",
        "PDFAIdentificationSchema": ".pdfa_identification_schema",
        "PDFUAIdentificationSchema": ".pdfua_identification_schema",
        "PhotoshopSchema": ".photoshop_schema",
        "XMPPageTextSchema": ".schema.xmp_page_text_schema",
        "TiffSchema": ".tiff_schema",
        "AbstractField": ".type",
        "AbstractSimpleProperty": ".type",
        "AbstractStructuredType": ".type",
        "AgentNameType": ".type",
        "ArrayProperty": ".type",
        "Attribute": ".type",
        "BooleanType": ".type",
        "Cardinality": ".type",
        "CFAPatternType": ".type",
        "ChoiceType": ".type",
        "ColorantType": ".type",
        "DateType": ".type",
        "DimensionsType": ".type",
        "FontType": ".type",
        "GPSCoordinateType": ".type",
        "GUIDType": ".type",
        "IntegerType": ".type",
        "LangAlt": ".type",
        "LayerType": ".type",
        "LocaleType": ".type",
        "MIMEType": ".type",
        "OECFType": ".type",
        "PartType": ".type",
        "ProperNameType": ".type",
        "RationalType": ".type",
        "RealType": ".type",
        "RenditionClassType": ".type",
        "ResourceEventType": ".type",
        "ResourceRefType": ".type",
        "TextType": ".type",
        "ThumbnailType": ".type",
        "TypeMapping": ".type",
        "URIType": ".type",
        "URLType": ".type",
        "VersionType": ".type",
        "XPathType": ".type",
        "XmpSerializationException": ".xml.xmp_serialization_exception",
        "JobType": ".xmp_basic_job_ticket_schema",
        "XMPBasicJobTicketSchema": ".xmp_basic_job_ticket_schema",
        "XMPBasicSchema": ".xmp_basic_schema",
        "XmpConstants": ".xmp_constants",
        "XMPMediaManagementSchema": ".xmp_media_management_schema",
        "XMPMetadata": ".xmp_metadata",
        "XMPageTextSchema": ".xmp_paged_text_schema",
        "XMPRightsManagementSchema": ".xmp_rights_management_schema",
        "XMPSchema": ".xmp_schema",
    },
)

__all__ = [
    "AbstractField",
    "AbstractSimpleProperty",
    "AbstractStructuredType",
    "AdobePDFSchema",
    "AgentNameType",
    "ArrayProperty",
    "Attribute",
    "BooleanType",
    "CFAPatternType",
    "Cardinality",
    "ChoiceType",
    "ColorantType",
    "DateConverter",
    "DateType",
    "DimensionsType",
    "DomXmpParser",
    "DublinCoreSchema",
    "ExifSchema",
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
    "BadFieldValueException",
    "PDFAExtensionSchema",
    "PDFAIdentificationSchema",
    "PDFUAIdentificationSchema",
    "PhotoshopSchema",
    "ProperNameType",
    "RationalType",
    "RealType",
    "RenditionClassType",
    "ResourceEventType",
    "ResourceRefType",
    "TextType",
    "ThumbnailType",
    "TiffSchema",
    "TypeMapping",
    "URIType",
    "URLType",
    "VersionType",
    "XMPBasicJobTicketSchema",
    "XMPBasicSchema",
    "XMPMediaManagementSchema",
    "XMPMetadata",
    "XMPPageTextSchema",
    "XMPRightsManagementSchema",
    "XMPSchema",
    "XMPageTextSchema",
    "XPathType",
    "XmpConstants",
    "XmpParsingException",
    "XmpSerializationException",
]

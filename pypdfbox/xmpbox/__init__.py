"""
pypdfbox.xmpbox — Python port of the Apache PDFBox xmpbox subproject.

Cluster #1 ships the XMP packet read path: ``XMPMetadata`` plus a
``DomXmpParser`` backed by ``xml.etree.ElementTree``. Schema dispatch
covers Dublin Core and XMP Basic; unknown namespaces fall back to a
plain :class:`XMPSchema`. Writing, ``TypeMapping``, and the rich
``AbstractField`` hierarchy are deferred to later clusters.
"""

from __future__ import annotations

from .adobe_pdf_schema import AdobePDFSchema
from .dom_xmp_parser import DomXmpParser, XmpParsingException
from .dublin_core_schema import DublinCoreSchema
from .exif_schema import ExifSchema
from .pdfa_extension_schema import PDFAExtensionSchema
from .pdfa_identification_schema import PDFAIdentificationSchema
from .pdfua_identification_schema import PDFUAIdentificationSchema
from .photoshop_schema import PhotoshopSchema
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
    MIMEType,
    ProperNameType,
    RationalType,
    RealType,
    ResourceEventType,
    ResourceRefType,
    TextType,
    ThumbnailType,
    TypeMapping,
    URIType,
)
from .xmp_basic_job_ticket_schema import JobType, XMPBasicJobTicketSchema
from .xmp_basic_schema import XMPBasicSchema
from .xmp_media_management_schema import XMPMediaManagementSchema
from .xmp_metadata import XMPMetadata
from .xmp_paged_text_schema import XMPageTextSchema
from .xmp_rights_management_schema import XMPRightsManagementSchema
from .xmp_schema import XMPSchema

__all__ = [
    "AbstractField",
    "AbstractSimpleProperty",
    "AbstractStructuredType",
    "AdobePDFSchema",
    "AgentNameType",
    "ArrayProperty",
    "Attribute",
    "BooleanType",
    "Cardinality",
    "ChoiceType",
    "ColorantType",
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
    "MIMEType",
    "PDFAExtensionSchema",
    "PDFAIdentificationSchema",
    "PDFUAIdentificationSchema",
    "PhotoshopSchema",
    "ProperNameType",
    "RationalType",
    "RealType",
    "ResourceEventType",
    "ResourceRefType",
    "TextType",
    "ThumbnailType",
    "TiffSchema",
    "TypeMapping",
    "URIType",
    "XMPBasicJobTicketSchema",
    "XMPBasicSchema",
    "XMPMediaManagementSchema",
    "XMPMetadata",
    "XMPRightsManagementSchema",
    "XMPSchema",
    "XMPageTextSchema",
    "XmpParsingException",
]

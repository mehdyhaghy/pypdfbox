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
from .pdfa_extension_schema import PDFAExtensionSchema
from .pdfa_identification_schema import PDFAIdentificationSchema
from .photoshop_schema import PhotoshopSchema
from .xmp_basic_job_ticket_schema import JobType, XMPBasicJobTicketSchema
from .xmp_basic_schema import XMPBasicSchema
from .xmp_media_management_schema import XMPMediaManagementSchema
from .xmp_metadata import XMPMetadata
from .xmp_paged_text_schema import XMPageTextSchema
from .xmp_rights_management_schema import XMPRightsManagementSchema
from .xmp_schema import XMPSchema

__all__ = [
    "AdobePDFSchema",
    "DomXmpParser",
    "DublinCoreSchema",
    "JobType",
    "PDFAExtensionSchema",
    "PDFAIdentificationSchema",
    "PhotoshopSchema",
    "XMPBasicJobTicketSchema",
    "XMPBasicSchema",
    "XMPMediaManagementSchema",
    "XMPMetadata",
    "XMPRightsManagementSchema",
    "XMPSchema",
    "XMPageTextSchema",
    "XmpParsingException",
]

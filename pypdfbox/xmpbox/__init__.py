"""
pypdfbox.xmpbox — Python port of the Apache PDFBox xmpbox subproject.

Cluster #1 ships the XMP packet read path: ``XMPMetadata`` plus a
``DomXmpParser`` backed by ``xml.etree.ElementTree``. Schema dispatch
covers Dublin Core and XMP Basic; unknown namespaces fall back to a
plain :class:`XMPSchema`. Writing, ``TypeMapping``, and the rich
``AbstractField`` hierarchy are deferred to later clusters.
"""

from __future__ import annotations

from .dom_xmp_parser import DomXmpParser, XmpParsingException
from .dublin_core_schema import DublinCoreSchema
from .xmp_basic_schema import XMPBasicSchema
from .xmp_metadata import XMPMetadata
from .xmp_schema import XMPSchema

__all__ = [
    "DomXmpParser",
    "DublinCoreSchema",
    "XMPBasicSchema",
    "XMPMetadata",
    "XMPSchema",
    "XmpParsingException",
]

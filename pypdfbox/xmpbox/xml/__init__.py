"""XMP XML parsing and serialisation helpers."""

from __future__ import annotations

from pypdfbox.xmpbox.xml.dom_helper import DomHelper
from pypdfbox.xmpbox.xml.namespace_finder import NamespaceFinder
from pypdfbox.xmpbox.xml.pdfa_extension_helper import PdfaExtensionHelper
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer

__all__ = ["DomHelper", "NamespaceFinder", "PdfaExtensionHelper", "XmpSerializer"]

"""Schema-side helpers ported from ``org.apache.xmpbox.schema``."""

from __future__ import annotations

from pypdfbox.xmpbox.exif_schema import ExifSchema
from pypdfbox.xmpbox.schema.xmp_page_text_schema import XMPPageTextSchema
from pypdfbox.xmpbox.schema.xmp_schema_factory import XMPSchemaFactory

__all__ = ["ExifSchema", "XMPPageTextSchema", "XMPSchemaFactory"]

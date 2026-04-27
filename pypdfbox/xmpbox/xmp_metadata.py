from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .xmp_schema import XMPSchema


# Constants ported from org.apache.xmpbox.XmpConstants. Surfaced as module-level
# names rather than a separate XmpConstants class because the upstream class is
# a private constant holder and Python prefers module constants.
RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
DEFAULT_XPACKET_BEGIN = "﻿"
DEFAULT_XPACKET_ID = "W5M0MpCehiHzreSzNTczkc9d"
DEFAULT_XPACKET_BYTES: str | None = None
DEFAULT_XPACKET_ENCODING = "UTF-8"
DEFAULT_XPACKET_END = "w"
DEFAULT_RDF_PREFIX = "rdf"
DEFAULT_RDF_LOCAL_NAME = "RDF"


class XMPMetadata:
    """
    Object representation of XMP metadata.

    Ported (subset) from ``org.apache.xmpbox.XMPMetadata``. This is a read-path
    container: it holds an ordered list of :class:`XMPSchema` instances plus the
    surrounding ``<?xpacket ...?>`` processing-instruction values. Schema
    lookup by namespace returns the first schema with that namespace URI,
    matching upstream behavior.

    Cluster #1 deviates from upstream by omitting the ``TypeMapping`` system
    and the per-property ``AbstractField`` hierarchy; properties are stored as
    plain strings, lists, or language-keyed dicts inside ``XMPSchema``.
    """

    def __init__(
        self,
        xpacket_begin: str | None = DEFAULT_XPACKET_BEGIN,
        xpacket_id: str | None = DEFAULT_XPACKET_ID,
        xpacket_bytes: str | None = DEFAULT_XPACKET_BYTES,
        xpacket_encoding: str | None = DEFAULT_XPACKET_ENCODING,
        xpacket_end: str = DEFAULT_XPACKET_END,
    ) -> None:
        self._xpacket_begin = xpacket_begin
        self._xpacket_id = xpacket_id
        self._xpacket_bytes = xpacket_bytes
        self._xpacket_encoding = xpacket_encoding
        self._xpacket_end_data = xpacket_end
        self._schemas: list[XMPSchema] = []

    # --- factory --------------------------------------------------------

    @classmethod
    def create_xmp_metadata(
        cls,
        xpacket_begin: str | None = DEFAULT_XPACKET_BEGIN,
        xpacket_id: str | None = DEFAULT_XPACKET_ID,
        xpacket_bytes: str | None = DEFAULT_XPACKET_BYTES,
        xpacket_encoding: str | None = DEFAULT_XPACKET_ENCODING,
    ) -> XMPMetadata:
        """Mirror of upstream ``XMPMetadata.createXMPMetadata`` factory."""
        return cls(xpacket_begin, xpacket_id, xpacket_bytes, xpacket_encoding)

    # --- xpacket accessors ---------------------------------------------

    def get_xpacket_begin(self) -> str | None:
        return self._xpacket_begin

    def get_xpacket_id(self) -> str | None:
        return self._xpacket_id

    def get_xpacket_bytes(self) -> str | None:
        return self._xpacket_bytes

    def get_xpacket_encoding(self) -> str | None:
        return self._xpacket_encoding

    def set_end_xpacket(self, data: str) -> None:
        self._xpacket_end_data = data

    def get_end_xpacket(self) -> str:
        return self._xpacket_end_data

    # --- schema management ---------------------------------------------

    def add_schema(self, schema: XMPSchema) -> None:
        self._schemas.append(schema)

    def get_all_schemas(self) -> list[XMPSchema]:
        # Upstream returns a defensive copy; mirror that.
        return list(self._schemas)

    def get_schema(self, namespace_or_class: str | type) -> XMPSchema | None:
        """
        Return the first schema matching either a namespace URI string or a
        schema subclass. Mirrors the two upstream ``getSchema`` overloads.
        """
        if isinstance(namespace_or_class, str):
            ns_uri = namespace_or_class
            for schema in self._schemas:
                if schema.get_namespace() == ns_uri:
                    return schema
            return None
        # class case
        cls = namespace_or_class
        ns_uri = getattr(cls, "NAMESPACE", None)
        if ns_uri is None:
            return None
        for schema in self._schemas:
            if isinstance(schema, cls) and schema.get_namespace() == ns_uri:
                return schema
        # Fallback: any schema that is an instance of cls.
        for schema in self._schemas:
            if isinstance(schema, cls):
                return schema
        return None

    def get_schema_by_prefix(self, prefix: str, ns_uri: str) -> XMPSchema | None:
        """Mirror of upstream ``getSchema(String prefix, String nsURI)``."""
        for schema in self._schemas:
            if schema.get_namespace() == ns_uri and schema.get_prefix() == prefix:
                return schema
        return None

    # --- typed convenience accessors -----------------------------------

    def get_dublin_core_schema(self) -> XMPSchema | None:
        from .dublin_core_schema import DublinCoreSchema

        return self.get_schema(DublinCoreSchema)

    def get_xmp_basic_schema(self) -> XMPSchema | None:
        from .xmp_basic_schema import XMPBasicSchema

        return self.get_schema(XMPBasicSchema)

    def get_pdf_identification_schema(self) -> XMPSchema | None:
        # Mirror of upstream ``XMPMetadata.getPDFIdentificationSchema``.
        from .pdfa_identification_schema import PDFAIdentificationSchema

        return self.get_schema(PDFAIdentificationSchema)

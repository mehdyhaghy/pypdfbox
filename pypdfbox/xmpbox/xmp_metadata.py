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
        # Upstream ``XMPMetadata`` exposes a ``read-only`` flag on the packet
        # (``<?xpacket … w?>`` vs ``r``). Cluster #1 stores the boolean directly
        # and keeps :attr:`_xpacket_end_data` as the source of truth for the
        # serialised form; see :meth:`is_read_only` / :meth:`set_read_only`.
        self._read_only: bool = xpacket_end == "r"

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

    def set_xpacket_begin(self, value: str | None) -> None:
        """Mirror of upstream ``setXpacketBegin`` (write-side companion)."""
        self._xpacket_begin = value

    def get_xpacket_id(self) -> str | None:
        return self._xpacket_id

    def set_xpacket_id(self, value: str | None) -> None:
        """Mirror of upstream ``setXpacketId`` (write-side companion)."""
        self._xpacket_id = value

    def get_xpacket_bytes(self) -> str | None:
        return self._xpacket_bytes

    def set_xpacket_bytes(self, value: str | None) -> None:
        """Mirror of upstream ``setXpacketBytes``."""
        self._xpacket_bytes = value

    def get_xpacket_encoding(self) -> str | None:
        return self._xpacket_encoding

    def set_xpacket_encoding(self, value: str | None) -> None:
        """Mirror of upstream ``setXpacketEncoding``."""
        self._xpacket_encoding = value

    def set_end_xpacket(self, data: str) -> None:
        self._xpacket_end_data = data
        self._read_only = data == "r"

    def get_end_xpacket(self) -> str:
        return self._xpacket_end_data

    # --- read-only flag (xpacket end="r"/"w") --------------------------

    def is_read_only(self) -> bool:
        """
        Mirror of upstream ``XMPMetadata.isReadOnly``. ``True`` when the packet
        was (or will be) serialised with ``<?xpacket end='r'?>``.
        """
        return self._read_only

    def set_read_only(self, value: bool) -> None:
        """
        Mirror of upstream ``setReadOnly(boolean)``. Also flips the underlying
        ``end='w'``/``end='r'`` marker so :meth:`get_end_xpacket` stays in sync.
        """
        self._read_only = bool(value)
        self._xpacket_end_data = "r" if self._read_only else "w"

    # --- rdf:about (document-level alias) ------------------------------

    def get_about(self) -> str | None:
        """
        Mirror of upstream ``XMPMetadata.getAbout``. Cluster #1 stores
        ``rdf:about`` per-schema (see :meth:`XMPSchema.get_about`); for the
        document-level alias we surface the first schema's ``rdf:about`` value
        so packets that share a single ``rdf:Description`` round-trip cleanly.
        Returns ``None`` when no schema has been added yet, mirroring upstream
        behavior of returning ``null`` for an empty packet.
        """
        for schema in self._schemas:
            value = schema.get_about_attribute()
            if value:
                return value
        return None

    def set_about(self, value: str) -> None:
        """
        Mirror of upstream ``XMPMetadata.setAbout``. Propagates ``rdf:about``
        to every registered schema so subsequent serialisations include it.
        """
        for schema in self._schemas:
            schema.set_about(value)

    # --- schema management ---------------------------------------------

    def add_schema(self, schema: XMPSchema) -> None:
        self._schemas.append(schema)

    def remove_schema(self, schema: XMPSchema) -> None:
        """
        Mirror of upstream ``XMPMetadata.removeSchema``. Silently no-ops when
        the schema instance is not currently registered, matching upstream
        ``List#remove(Object)`` semantics.
        """
        try:
            self._schemas.remove(schema)
        except ValueError:
            pass

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

    def add_dublin_core_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``addDublinCoreSchema``: install (or reuse) a
        :class:`DublinCoreSchema` and return it. Idempotent — repeat calls
        return the existing schema rather than stacking duplicates.
        """
        from .dublin_core_schema import DublinCoreSchema

        existing = self.get_schema(DublinCoreSchema)
        if existing is not None:
            return existing
        schema = DublinCoreSchema(self)
        self.add_schema(schema)
        return schema

    def get_xmp_basic_schema(self) -> XMPSchema | None:
        from .xmp_basic_schema import XMPBasicSchema

        return self.get_schema(XMPBasicSchema)

    def add_xmp_basic_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``addXMPBasicSchema``: install (or reuse) an
        :class:`XMPBasicSchema` and return it.
        """
        from .xmp_basic_schema import XMPBasicSchema

        existing = self.get_schema(XMPBasicSchema)
        if existing is not None:
            return existing
        schema = XMPBasicSchema(self)
        self.add_schema(schema)
        return schema

    def get_pdf_identification_schema(self) -> XMPSchema | None:
        # Mirror of upstream ``XMPMetadata.getPDFIdentificationSchema``.
        from .pdfa_identification_schema import PDFAIdentificationSchema

        return self.get_schema(PDFAIdentificationSchema)

    def get_pdfa_identification_schema(self) -> XMPSchema | None:
        """Upstream-named alias of :meth:`get_pdf_identification_schema`."""
        return self.get_pdf_identification_schema()

    def add_pdfa_identification_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``addPDFAIdentificationSchema``: install (or reuse)
        a :class:`PDFAIdentificationSchema` and return it.
        """
        from .pdfa_identification_schema import PDFAIdentificationSchema

        existing = self.get_schema(PDFAIdentificationSchema)
        if existing is not None:
            return existing
        schema = PDFAIdentificationSchema(self)
        self.add_schema(schema)
        return schema

    # --- XMP Rights Management schema --------------------------------

    def get_xmp_rights_management_schema(self) -> XMPSchema | None:
        # Mirror of upstream ``XMPMetadata.getXMPRightsManagementSchema``.
        from .xmp_rights_management_schema import XMPRightsManagementSchema

        return self.get_schema(XMPRightsManagementSchema)

    def add_xmp_rights_management_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``addXMPRightsManagementSchema``: install (or reuse)
        an :class:`XMPRightsManagementSchema` and return it.
        """
        from .xmp_rights_management_schema import XMPRightsManagementSchema

        existing = self.get_schema(XMPRightsManagementSchema)
        if existing is not None:
            return existing
        schema = XMPRightsManagementSchema(self)
        self.add_schema(schema)
        return schema

    # --- XMP Media Management schema ---------------------------------

    def get_xmp_media_management_schema(self) -> XMPSchema | None:
        # Mirror of upstream ``XMPMetadata.getXMPMediaManagementSchema``.
        from .xmp_media_management_schema import XMPMediaManagementSchema

        return self.get_schema(XMPMediaManagementSchema)

    def add_xmp_media_management_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``addXMPMediaManagementSchema``: install (or reuse)
        an :class:`XMPMediaManagementSchema` and return it.
        """
        from .xmp_media_management_schema import XMPMediaManagementSchema

        existing = self.get_schema(XMPMediaManagementSchema)
        if existing is not None:
            return existing
        schema = XMPMediaManagementSchema(self)
        self.add_schema(schema)
        return schema

    # --- Adobe PDF schema --------------------------------------------

    def get_adobe_pdf_schema(self) -> XMPSchema | None:
        """Mirror of upstream ``getAdobePDFSchema``."""
        from .adobe_pdf_schema import AdobePDFSchema

        return self.get_schema(AdobePDFSchema)

    def get_pdf_schema(self) -> XMPSchema | None:
        """Upstream-named alias of :meth:`get_adobe_pdf_schema`."""
        return self.get_adobe_pdf_schema()

    def add_adobe_pdf_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``addAdobePDFSchema`` / ``createAndAddAdobePDFSchema``:
        install (or reuse) an :class:`AdobePDFSchema` and return it. Idempotent —
        repeat calls return the existing schema rather than stacking duplicates.
        """
        from .adobe_pdf_schema import AdobePDFSchema

        existing = self.get_schema(AdobePDFSchema)
        if existing is not None:
            return existing
        schema = AdobePDFSchema(self)
        self.add_schema(schema)
        return schema

    def create_and_add_adobe_pdf_schema(self) -> XMPSchema:
        """Upstream-named alias of :meth:`add_adobe_pdf_schema`."""
        return self.add_adobe_pdf_schema()

    def add_pdf_basic_schema(self) -> XMPSchema:
        """Upstream-compatible alias of :meth:`add_adobe_pdf_schema`."""
        return self.add_adobe_pdf_schema()

    # --- PDF/A extension schema -----------------------------------------

    def get_pdfa_extension_schema(self) -> XMPSchema | None:
        """
        Mirror of upstream ``getPDFExtensionSchema`` / ``getPDFAExtensionSchema``.
        Returns the registered :class:`PDFAExtensionSchema` instance if the
        packet declares one, or ``None`` otherwise.
        """
        from .pdfa_extension_schema import PDFAExtensionSchema

        return self.get_schema(PDFAExtensionSchema)

    def add_pdfa_extension_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``addPDFAExtensionSchema``: install (or reuse) a
        :class:`PDFAExtensionSchema` and return it. Idempotent — repeat calls
        return the existing schema rather than stacking duplicates.
        """
        from .pdfa_extension_schema import PDFAExtensionSchema

        existing = self.get_schema(PDFAExtensionSchema)
        if existing is not None:
            return existing
        schema = PDFAExtensionSchema(self)
        self.add_schema(schema)
        return schema

    def add_pdf_extension_schema(self) -> XMPSchema:
        """Upstream-compatible alias of :meth:`add_pdfa_extension_schema`."""
        return self.add_pdfa_extension_schema()

    # --- XMP Basic Job Ticket schema ----------------------------------

    def get_basic_job_ticket_schema(self) -> XMPSchema | None:
        """Mirror of upstream ``getBasicJobTicketSchema``."""
        from .xmp_basic_job_ticket_schema import XMPBasicJobTicketSchema

        return self.get_schema(XMPBasicJobTicketSchema)

    def create_and_add_basic_job_ticket_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``createAndAddBasicJobTicketSchema``: install a
        fresh :class:`XMPBasicJobTicketSchema` and return it. Upstream creates
        unconditionally; cluster #1 keeps that behavior so the method always
        returns a newly-built instance.
        """
        from .xmp_basic_job_ticket_schema import XMPBasicJobTicketSchema

        schema = XMPBasicJobTicketSchema(self)
        self.add_schema(schema)
        return schema

    def add_xmp_basic_job_ticket_schema(self) -> XMPSchema:
        """
        Upstream-name-friendly alias used in pypdfbox cluster #1 to mirror the
        idempotent add pattern used by sibling schemas (returns the existing
        instance on repeat calls rather than stacking duplicates).
        """
        from .xmp_basic_job_ticket_schema import XMPBasicJobTicketSchema

        existing = self.get_schema(XMPBasicJobTicketSchema)
        if existing is not None:
            return existing
        return self.create_and_add_basic_job_ticket_schema()

    # --- XMP Paged-Text schema ----------------------------------------

    def get_page_text_schema(self) -> XMPSchema | None:
        """Mirror of upstream ``XMPMetadata.getPageTextSchema``."""
        from .xmp_paged_text_schema import XMPageTextSchema

        return self.get_schema(XMPageTextSchema)

    def create_and_add_page_text_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``createAndAddPageTextSchema``: install a fresh
        :class:`XMPageTextSchema` (with ``rdf:about=""``) and return it.
        Upstream creates unconditionally; cluster #1 keeps that behavior so
        the method always returns a newly-built instance.
        """
        from .xmp_paged_text_schema import XMPageTextSchema

        schema = XMPageTextSchema(self)
        schema.set_about_as_simple("")
        self.add_schema(schema)
        return schema

    # --- Photoshop schema ---------------------------------------------

    def get_photoshop_schema(self) -> XMPSchema | None:
        """Mirror of upstream ``XMPMetadata.getPhotoshopSchema``."""
        from .photoshop_schema import PhotoshopSchema

        return self.get_schema(PhotoshopSchema)

    def add_photoshop_schema(self) -> XMPSchema:
        """
        Mirror of upstream ``addPhotoshopSchema``: install (or reuse) a
        :class:`PhotoshopSchema` and return it. Idempotent — repeat calls
        return the existing schema rather than stacking duplicates.
        """
        from .photoshop_schema import PhotoshopSchema

        existing = self.get_schema(PhotoshopSchema)
        if existing is not None:
            return existing
        schema = PhotoshopSchema(self)
        self.add_schema(schema)
        return schema

    def create_and_add_photoshop_schema(self) -> XMPSchema:
        """
        Upstream-compatible alias of :meth:`add_photoshop_schema`. Mirrors the
        ``createAndAdd*`` naming the upstream class uses for some of its
        schema accessors.
        """
        return self.add_photoshop_schema()

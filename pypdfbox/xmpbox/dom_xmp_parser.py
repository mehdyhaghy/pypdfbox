from __future__ import annotations

import re
from enum import Enum
from typing import IO
from xml.etree import ElementTree as ET

from .adobe_pdf_schema import AdobePDFSchema
from .dublin_core_schema import DublinCoreSchema
from .exif_schema import ExifSchema
from .pdfa_extension_schema import PDFAExtensionSchema
from .pdfa_identification_schema import PDFAIdentificationSchema
from .pdfua_identification_schema import PDFUAIdentificationSchema
from .photoshop_schema import PhotoshopSchema
from .tiff_schema import TiffSchema
from .xmp_basic_schema import XMPBasicSchema
from .xmp_media_management_schema import XMPMediaManagementSchema
from .xmp_metadata import RDF_NAMESPACE, XMPMetadata
from .xmp_paged_text_schema import XMPageTextSchema
from .xmp_rights_management_schema import XMPRightsManagementSchema
from .xmp_schema import X_DEFAULT, XMPSchema


class XmpParsingException(ValueError):
    """Raised when an XMP packet is malformed or cannot be parsed.

    Mirrors ``org.apache.xmpbox.xml.XmpParsingException`` (PDFBox 3.0.x): an
    ``ErrorType`` discriminator categorises the failure mode so callers can
    branch on the cause without parsing the message string. Constructing with
    only a message (no error type) is also supported for backward
    compatibility — ``error_type`` defaults to :attr:`ErrorType.UNDEFINED` in
    that case.
    """

    class ErrorType(Enum):
        """Mirrors upstream ``XmpParsingException.ErrorType``."""

        UNDEFINED = "Undefined"
        CONFIGURATION = "Configuration"
        XPACKET_BAD_START = "XpacketBadStart"
        XPACKET_BAD_END = "XpacketBadEnd"
        NO_ROOT_ELEMENT = "NoRootElement"
        NO_SCHEMA = "NoSchema"
        INVALID_PDFA_SCHEMA = "InvalidPdfaSchema"
        NO_TYPE = "NoType"
        INVALID_TYPE = "InvalidType"
        FORMAT = "Format"
        NO_VALUE_TYPE = "NoValueType"
        REQUIRED_PROPERTY = "RequiredProperty"
        INVALID_PREFIX = "InvalidPrefix"

    def __init__(
        self,
        error_or_message: XmpParsingException.ErrorType | str,
        message: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if isinstance(error_or_message, XmpParsingException.ErrorType):
            error = error_or_message
            msg = "" if message is None else message
        else:
            # Backward-compatible single-message form: defaults to UNDEFINED.
            error = XmpParsingException.ErrorType.UNDEFINED
            msg = error_or_message
        super().__init__(msg)
        self._error_type = error
        if cause is not None:
            self.__cause__ = cause

    def get_error_type(self) -> XmpParsingException.ErrorType:
        """Returns the categorical error type (upstream ``getErrorType``)."""
        return self._error_type

    @property
    def error_type(self) -> XmpParsingException.ErrorType:
        """Pythonic accessor for :meth:`get_error_type`."""
        return self._error_type


# XML namespace constants used by the parser.
_RDF_NS = RDF_NAMESPACE
_XML_NS = "http://www.w3.org/XML/1998/namespace"

# Built-in schema dispatch table: namespace URI -> XMPSchema subclass.
_SCHEMA_REGISTRY: dict[str, type[XMPSchema]] = {
    DublinCoreSchema.NAMESPACE: DublinCoreSchema,
    XMPBasicSchema.NAMESPACE: XMPBasicSchema,
    PDFAIdentificationSchema.NAMESPACE: PDFAIdentificationSchema,
    PDFUAIdentificationSchema.NAMESPACE: PDFUAIdentificationSchema,
    PDFAExtensionSchema.NAMESPACE: PDFAExtensionSchema,
    XMPMediaManagementSchema.NAMESPACE: XMPMediaManagementSchema,
    XMPRightsManagementSchema.NAMESPACE: XMPRightsManagementSchema,
    XMPageTextSchema.NAMESPACE: XMPageTextSchema,
    PhotoshopSchema.NAMESPACE: PhotoshopSchema,
    AdobePDFSchema.NAMESPACE: AdobePDFSchema,
    TiffSchema.NAMESPACE: TiffSchema,
    ExifSchema.NAMESPACE: ExifSchema,
}


# Match the <?xpacket begin="..." id="..." ?> processing instruction. Whitespace
# and attribute order are intentionally permissive; real packets are not always
# emitted in the canonical serializer order.
_XPACKET_BEGIN_RE = re.compile(
    rb"<\?xpacket\b(?=[^?]*\bbegin\s*=)(?=[^?]*\bid\s*=)([^?]*)\?>",
    re.DOTALL,
)
_XPACKET_ATTR_RE = re.compile(
    rb"\b(begin|id|bytes|encoding)\s*=\s*([\"'])(.*?)\2",
    re.DOTALL,
)
_XPACKET_END_RE = re.compile(rb"<\?xpacket\s+end\s*=\s*[\"']([^\"']*)[\"']\s*\?>")


def _strip_qname(tag: str) -> tuple[str, str]:
    """Split an ``ElementTree`` qualified-name ``{ns}local`` into (ns, local)."""
    if tag.startswith("{"):
        end = tag.find("}")
        return tag[1:end], tag[end + 1 :]
    return "", tag


def _parse_xpacket_attributes(raw_attrs: bytes) -> dict[str, str]:
    return {
        name.decode("ascii"): value.decode("utf-8", errors="replace")
        for name, _quote, value in _XPACKET_ATTR_RE.findall(raw_attrs)
    }


class DomXmpParser:
    """
    Read-only XMP packet parser.

    Ported (subset) from ``org.apache.xmpbox.xml.DomXmpParser`` (PDFBox 3.0).
    Backed by the Python stdlib ``xml.etree.ElementTree``; no external XML
    dependency is added (see CLAUDE.md library policy / PRD §3.7).

    Behavior:

      * Accepts ``bytes``, ``bytearray``, ``str``, or any binary stream.
      * Strips the leading ``<?xpacket begin="..." id="..."?>`` processing
        instruction, captures its values onto the returned :class:`XMPMetadata`,
        and strips the trailing ``<?xpacket end="..."?>``. The bare RDF/XML
        between these is what gets handed to ElementTree, which mirrors how
        upstream extracts the packet before calling its DOM builder.
      * Walks every ``rdf:Description`` block. Each block's namespace
        attributes drive schema dispatch via :data:`_SCHEMA_REGISTRY`; unknown
        namespaces fall back to a plain :class:`XMPSchema`.
      * For each schema, both attribute-form properties (``dc:format="…"``)
        and element-form properties (``<dc:title>…</dc:title>``) are extracted.
        ``rdf:Bag`` / ``rdf:Seq`` / ``rdf:Alt`` collections become Python
        ``list[str]`` / ``list[str]`` / ``dict[str, str]`` (lang-keyed).
    """

    def __init__(self) -> None:
        # Upstream DomXmpParser exposes a strict-parsing toggle and a
        # throw-on-invalid-xmp toggle. Strict mode is a deferred behavior in
        # this port (we currently always parse permissively), so the flag is
        # stored but not yet consumed by the parse pipeline.
        self._strict_parsing: bool = True
        self._throw_exception_on_invalid_xmp: bool = False

    # ------------------------------------------------------------------
    # public API (upstream-named entry points)
    # ------------------------------------------------------------------

    def parse(
        self, source: bytes | bytearray | memoryview | str | IO[bytes]
    ) -> XMPMetadata:
        raw = self._read_bytes(source)
        body, xpacket_begin, xpacket_id, xpacket_bytes, xpacket_encoding, xpacket_end = (
            self._extract_packet(raw)
        )

        try:
            # ``fromstring`` accepts bytes; the XML declaration's encoding is
            # honored by the underlying expat parser.
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise XmpParsingException(
                XmpParsingException.ErrorType.FORMAT,
                f"malformed XMP packet: {exc}",
            ) from exc

        rdf = self._find_rdf_root(root)
        if rdf is None:
            raise XmpParsingException(
                XmpParsingException.ErrorType.NO_ROOT_ELEMENT,
                "no rdf:RDF element found in XMP packet",
            )

        metadata = XMPMetadata(
            xpacket_begin=xpacket_begin,
            xpacket_id=xpacket_id,
            xpacket_bytes=xpacket_bytes,
            xpacket_encoding=xpacket_encoding,
            xpacket_end=xpacket_end if xpacket_end is not None else "w",
        )

        # Group rdf:Description elements by namespace so a packet that splits a
        # single schema across multiple Descriptions still yields one schema
        # per namespace (this is how PDFBOX-5976 is shaped).
        per_ns: dict[str, XMPSchema] = {}
        for desc in rdf.findall(f"{{{_RDF_NS}}}Description"):
            self._merge_description(desc, metadata, per_ns)

        for schema in per_ns.values():
            metadata.add_schema(schema)
        return metadata

    def parse_input(
        self, source: bytes | bytearray | memoryview | str | IO[bytes]
    ) -> XMPMetadata:
        """Upstream alias for :meth:`parse`."""
        return self.parse(source)

    # ------------------------------------------------------------------
    # strict-parsing toggle (placeholder; not yet consumed — see CHANGES.md)
    # ------------------------------------------------------------------

    def set_strict_parsing(self, b: bool) -> None:
        """Toggle strict parsing. Stored but not yet enforced in this port."""
        self._strict_parsing = bool(b)

    def is_strict_parsing(self) -> bool:
        """Return the current strict-parsing flag."""
        return self._strict_parsing

    def set_throw_exception_on_invalid_xmp(self, b: bool) -> None:
        """Upstream alias for :meth:`set_strict_parsing`."""
        self.set_strict_parsing(b)

    def is_throw_exception_on_invalid_xmp(self) -> bool:
        """Upstream alias for :meth:`is_strict_parsing`."""
        return self.is_strict_parsing()

    # ------------------------------------------------------------------
    # namespace registry introspection
    # ------------------------------------------------------------------

    def get_namespace_table(self) -> dict[str, str]:
        """
        Return the namespace prefix → URI map currently registered with the
        parser. Mirrors ``DomXmpParser#getNamespaceTable`` in upstream.
        """
        table: dict[str, str] = {
            "rdf": _RDF_NS,
            "xml": _XML_NS,
        }
        for ns_uri, schema_cls in _SCHEMA_REGISTRY.items():
            prefix = getattr(schema_cls, "PREFERRED_PREFIX", None)
            if prefix:
                table[prefix] = ns_uri
        return table

    # ------------------------------------------------------------------
    # upstream-named aliases for internal element parsers
    # ------------------------------------------------------------------

    def parse_describe_element(
        self,
        desc: ET.Element,
        metadata: XMPMetadata,
        per_ns: dict[str, XMPSchema] | None = None,
    ) -> dict[str, XMPSchema]:
        """
        Upstream-named entry point that parses a single ``rdf:Description``
        element into the supplied ``per_ns`` accumulator (created lazily if
        omitted). Returns the accumulator so callers can chain.
        """
        if per_ns is None:
            per_ns = {}
        self._merge_description(desc, metadata, per_ns)
        return per_ns

    def parse_property(self, element: ET.Element) -> object:
        """
        Upstream alias for the internal property-value parser. Returns a
        ``str``, ``list[str]`` (Bag/Seq), or ``dict[str, str]`` (Alt).
        """
        return self._parse_property_value(element)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_bytes(source: bytes | bytearray | memoryview | str | IO[bytes]) -> bytes:
        if isinstance(source, (bytes, bytearray, memoryview)):
            return bytes(source)
        if isinstance(source, str):
            return source.encode("utf-8")
        # Treat as a binary file-like object.
        data = source.read()
        if isinstance(data, str):
            return data.encode("utf-8")
        return bytes(data)

    @staticmethod
    def _extract_packet(
        raw: bytes,
    ) -> tuple[bytes, str | None, str | None, str | None, str | None, str | None]:
        """
        Pull out the xpacket envelope. Returns the inner body plus the four
        xpacket attributes (begin/id/bytes/encoding) and the trailing end value.
        If no xpacket PI is present (some PDFs embed bare RDF), the input is
        returned unchanged.
        """
        body = raw.lstrip(b"\xef\xbb\xbf").lstrip()
        begin_match = _XPACKET_BEGIN_RE.search(body)
        xpacket_begin: str | None = None
        xpacket_id: str | None = None
        xpacket_bytes: str | None = None
        xpacket_encoding: str | None = None
        xpacket_end: str | None = None

        if begin_match:
            attrs = _parse_xpacket_attributes(begin_match.group(1))
            xpacket_begin = attrs.get("begin")
            xpacket_id = attrs.get("id")
            xpacket_bytes = attrs.get("bytes")
            xpacket_encoding = attrs.get("encoding")
            body = body[begin_match.end() :]

        end_match = _XPACKET_END_RE.search(body)
        if end_match:
            xpacket_end = end_match.group(1).decode("utf-8", errors="replace")
            body = body[: end_match.start()]

        return body.strip(), xpacket_begin, xpacket_id, xpacket_bytes, xpacket_encoding, xpacket_end

    @staticmethod
    def _find_rdf_root(root: ET.Element) -> ET.Element | None:
        ns, local = _strip_qname(root.tag)
        if ns == _RDF_NS and local == "RDF":
            return root
        # x:xmpmeta wrapper case: the rdf:RDF lives one level down.
        rdf = root.find(f"{{{_RDF_NS}}}RDF")
        return rdf

    def _merge_description(
        self,
        desc: ET.Element,
        metadata: XMPMetadata,
        per_ns: dict[str, XMPSchema],
    ) -> None:
        about = desc.get(f"{{{_RDF_NS}}}about", "")

        # Attribute-form properties: every attribute on the rdf:Description
        # whose namespace is not RDF and not XML is a simple text property on
        # the schema for that namespace.
        for qname, value in desc.attrib.items():
            ns, local = _strip_qname(qname)
            if ns in ("", _RDF_NS, _XML_NS):
                continue
            schema = self._schema_for(ns, local, desc, metadata, per_ns, about)
            schema.set_text_property_value(local, value)

        # Element-form properties: each direct child whose namespace is not RDF
        # is a property on the schema for that namespace.
        for child in desc:
            ns, local = _strip_qname(child.tag)
            if ns == _RDF_NS:
                continue
            schema = self._schema_for(ns, local, desc, metadata, per_ns, about)
            parsed_value = self._parse_property_value(child)
            self._assign(schema, local, parsed_value)

    @staticmethod
    def _schema_for(
        ns: str,
        local_name_for_prefix_hint: str,  # noqa: ARG004 - reserved for future heuristics
        desc: ET.Element,
        metadata: XMPMetadata,
        per_ns: dict[str, XMPSchema],
        about: str,
    ) -> XMPSchema:
        existing = per_ns.get(ns)
        if existing is not None:
            return existing
        cls = _SCHEMA_REGISTRY.get(ns, XMPSchema)
        if cls is XMPSchema:
            # Plain schema needs explicit namespace. Prefix is best-effort:
            # infer it from the description element's xmlns map by scanning
            # attributes — ElementTree drops xmlns declarations from .attrib,
            # so we fall back to "ns0" if nothing better is available.
            schema = XMPSchema(metadata, namespace_uri=ns, prefix="ns0")
        else:
            schema = cls(metadata)
        schema.set_about(about)
        per_ns[ns] = schema
        return schema

    def _parse_property_value(self, element: ET.Element) -> object:
        """
        Determine whether ``element`` is a simple text value, a Bag/Seq/Alt
        container, a struct, or an attribute-only resource, and return the
        appropriate Python representation.
        """
        # rdf:Bag / rdf:Seq / rdf:Alt container as the only child.
        container = self._find_rdf_container(element)
        if container is not None:
            ns, local = _strip_qname(container.tag)
            items: list[ET.Element] = list(container.findall(f"{{{_RDF_NS}}}li"))
            if local == "Alt":
                lang_map: dict[str, str] = {}
                for li in items:
                    lang = li.get(f"{{{_XML_NS}}}lang") or X_DEFAULT
                    lang_map[lang] = (li.text or "").strip()
                return lang_map
            # Bag / Seq -> list[str]; preserve order for Seq, list order is fine
            # for Bag too (we expose a list, not a multiset).
            return [(li.text or "").strip() for li in items]

        # rdf:resource attribute (an inline reference)
        resource = element.get(f"{{{_RDF_NS}}}resource")
        if resource is not None and not list(element):
            return resource

        # Simple text value.
        return (element.text or "").strip()

    @staticmethod
    def _find_rdf_container(element: ET.Element) -> ET.Element | None:
        for child in element:
            ns, local = _strip_qname(child.tag)
            if ns == _RDF_NS and local in ("Bag", "Seq", "Alt"):
                return child
        return None

    @staticmethod
    def _assign(schema: XMPSchema, local_name: str, value: object) -> None:
        if isinstance(value, dict):
            for lang, v in value.items():
                schema.set_unqualified_language_property_value(local_name, lang, v)
        elif isinstance(value, list):
            for item in value:
                schema.add_qualified_bag_value(local_name, item)
        else:
            schema.set_text_property_value(local_name, str(value))


# Convenience module-level wrapper to mirror upstream usage patterns.
def parse(source: bytes | bytearray | memoryview | str | IO[bytes]) -> XMPMetadata:
    return DomXmpParser().parse(source)


__all__ = ["DomXmpParser", "XmpParsingException", "parse"]

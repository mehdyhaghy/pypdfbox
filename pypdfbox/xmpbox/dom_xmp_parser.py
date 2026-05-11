from __future__ import annotations

import re
from enum import Enum
from io import BytesIO
from typing import IO, cast
from xml.etree import ElementTree as ET

from .adobe_pdf_schema import AdobePDFSchema
from .dublin_core_schema import DublinCoreSchema
from .exif_schema import ExifSchema
from .pdfa_extension_schema import PDFAExtensionSchema
from .pdfa_identification_schema import PDFAIdentificationSchema
from .pdfua_identification_schema import PDFUAIdentificationSchema
from .photoshop_schema import PhotoshopSchema
from .tiff_schema import TiffSchema
from .type import (
    AbstractStructuredType,
    ArrayProperty,
    Cardinality,
    LayerType,
)
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

# Built-in typed-array element registry.
#
# Mirrors upstream ``TypeMapping#getStructuredTypeName`` /
# ``PropertyType(card = Seq, type = Layer)`` lookups: when an
# ``rdf:Bag`` / ``rdf:Seq`` / ``rdf:Alt`` lives under a known
# ``(namespace, property-local-name)`` slot whose typed element class is
# registered here, the parser builds typed ``AbstractStructuredType``
# instances out of the ``rdf:li`` children and stores them inside an
# :class:`ArrayProperty` (with the appropriate cardinality), exactly the
# way upstream ``manageArray`` + ``parseLiElement`` would.
#
# Keys are ``(schema namespace URI, property local-name)``; values are
# ``(element class, cardinality)``. The element class must subclass
# :class:`AbstractStructuredType` and expose a ``_FIELD_TYPES`` mapping
# so :meth:`AbstractStructuredType.add_simple_property` knows how to wrap
# each child value. Unknown slots fall through to the legacy plain-list
# / plain-dict representation.
# The cardinality string is the literal name (``"Bag"`` / ``"Seq"`` /
# ``"Alt"``) rather than a :class:`Cardinality` enum member because the
# enum's ``Bag`` / ``Seq`` / ``Alt`` members share the same value
# (``True``) — Python collapses them into a single canonical alias,
# losing the per-flavour name lookup. The literal string survives that
# collapse.
_TYPED_ARRAY_REGISTRY: dict[
    tuple[str, str], tuple[type[AbstractStructuredType], str]
] = {
    (PhotoshopSchema.NAMESPACE, PhotoshopSchema.TEXT_LAYERS): (
        LayerType,
        "Seq",
    ),
}


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
        # throw-on-invalid-xmp toggle. Strict mode currently enforces known
        # property names on schemas that expose a ``KNOWN_PROPERTIES`` surface.
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
        namespace_prefixes = self._collect_namespace_prefixes(body)

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
            self._merge_description(desc, metadata, per_ns, namespace_prefixes)

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
        """Toggle strict parsing."""
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
        self._merge_description(desc, metadata, per_ns, {})
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

    @staticmethod
    def _collect_namespace_prefixes(body: bytes) -> dict[str, str]:
        """
        Return namespace URI -> first prefix seen in the packet.

        ``ElementTree`` expands element names to ``{uri}local`` and drops the
        source ``xmlns`` declarations from ``Element.attrib``. The parser needs
        this side table for fallback schemas whose prefixes are not known ahead
        of time.
        """
        prefixes: dict[str, str] = {}
        try:
            for _event, ns in ET.iterparse(BytesIO(body), events=("start-ns",)):
                prefix, uri = cast(tuple[str, str], ns)
                prefixes.setdefault(uri, prefix)
        except ET.ParseError:
            # Preserve the main parse path's existing FORMAT exception message.
            return {}
        return prefixes

    def _merge_description(
        self,
        desc: ET.Element,
        metadata: XMPMetadata,
        per_ns: dict[str, XMPSchema],
        namespace_prefixes: dict[str, str],
    ) -> None:
        about = desc.get(f"{{{_RDF_NS}}}about", "")

        # Attribute-form properties: every attribute on the rdf:Description
        # whose namespace is not RDF and not XML is a simple text property on
        # the schema for that namespace.
        for qname, value in desc.attrib.items():
            ns, local = _strip_qname(qname)
            if ns in ("", _RDF_NS, _XML_NS):
                continue
            schema = self._schema_for(
                ns, local, desc, metadata, per_ns, about, namespace_prefixes
            )
            self._validate_strict_property(schema, ns, local)
            schema.set_text_property_value(local, value)

        # Element-form properties: each direct child whose namespace is not RDF
        # is a property on the schema for that namespace.
        for child in desc:
            ns, local = _strip_qname(child.tag)
            if ns == _RDF_NS:
                continue
            schema = self._schema_for(
                ns, local, desc, metadata, per_ns, about, namespace_prefixes
            )
            self._validate_strict_property(schema, ns, local)
            # Typed-array path: if this (namespace, local-name) slot has a
            # registered structured element type, port upstream
            # ``manageArray`` + ``parseLiElement`` and install an
            # :class:`ArrayProperty` of typed instances on the schema. Falls
            # back to the legacy plain-list / plain-dict path when no entry
            # is registered or the element shape doesn't match.
            typed_array = self._try_parse_typed_array(child, ns, local, schema)
            if typed_array is not None:
                typed_array.set_property_name(local)
                # ``ArrayProperty`` does not expose ``get_value`` so the
                # generic ``XMPSchema.add_property`` duck-typing path
                # rejects it. Write through the internal slot directly,
                # matching the way typed setters (e.g.
                # ``PhotoshopSchema.set_text_layers_property``) install an
                # array under the upstream local name.
                schema._properties[local] = typed_array  # noqa: SLF001
                continue
            parsed_value = self._parse_property_value(child)
            self._assign(schema, local, parsed_value)

    def _validate_strict_property(
        self, schema: XMPSchema, ns: str, local: str
    ) -> None:
        if not self._strict_parsing:
            return
        known = getattr(schema, "KNOWN_PROPERTIES", None)
        if known is not None and local not in known:
            raise XmpParsingException(
                XmpParsingException.ErrorType.INVALID_TYPE,
                f"No type defined for {{{ns}}}{local}",
            )

    @staticmethod
    def _schema_for(
        ns: str,
        local_name_for_prefix_hint: str,  # noqa: ARG004 - reserved for future heuristics
        desc: ET.Element,
        metadata: XMPMetadata,
        per_ns: dict[str, XMPSchema],
        about: str,
        namespace_prefixes: dict[str, str],
    ) -> XMPSchema:
        existing = per_ns.get(ns)
        if existing is not None:
            return existing
        cls = _SCHEMA_REGISTRY.get(ns, XMPSchema)
        if cls is XMPSchema:
            # Plain schema needs explicit namespace. Prefix comes from
            # ``start-ns`` events because ElementTree drops xmlns declarations
            # from ``Element.attrib``.
            schema = XMPSchema(
                metadata,
                namespace_uri=ns,
                prefix=namespace_prefixes.get(ns) or "ns0",
            )
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

    def _try_parse_typed_array(
        self,
        element: ET.Element,
        ns: str,
        local: str,
        schema: XMPSchema,
    ) -> ArrayProperty | None:
        """
        If ``(ns, local)`` matches a registered typed-array slot, port
        upstream ``manageArray`` + ``parseLiElement``: build an
        :class:`ArrayProperty` of typed
        :class:`AbstractStructuredType` instances out of the contained
        ``rdf:li`` children and return it. Returns ``None`` when the slot
        is not registered, the element does not enclose a
        ``Bag``/``Seq``/``Alt`` container, or no ``rdf:li`` children are
        present (so the legacy plain-list code path can take over).
        """
        entry = _TYPED_ARRAY_REGISTRY.get((ns, local))
        if entry is None:
            return None
        element_cls, cardinality_name = entry
        container = self._find_rdf_container(element)
        if container is None:
            return None
        container_ns, container_local = _strip_qname(container.tag)
        if container_ns != _RDF_NS:
            return None
        if container_local != cardinality_name:
            # Upstream raises FORMAT in strict mode; we silently fall back
            # to the plain-list code path because the parsed value still
            # round-trips for callers that don't reach for the typed view.
            return None
        lis = list(container.findall(f"{{{_RDF_NS}}}li"))
        if not lis:
            return None
        # Map the canonical cardinality-name string back to the right
        # :class:`Cardinality` member. The enum collapses Bag/Seq/Alt
        # into a single alias under the hood — :func:`getattr` here
        # always returns the canonical (Bag) member but that is fine for
        # the array's :meth:`is_array` semantics; the cardinality-name
        # is what callers introspect (``get_array_type().name``).
        cardinality = getattr(Cardinality, cardinality_name)
        array = ArrayProperty(
            schema.get_metadata(),
            ns,
            getattr(schema, "_prefix", None),
            local,
            cardinality,
        )
        for li in lis:
            instance = self._build_structured_from_li(li, element_cls, schema)
            if instance is not None:
                array.add_property(instance)
        return array

    def _build_structured_from_li(
        self,
        li: ET.Element,
        element_cls: type[AbstractStructuredType],
        schema: XMPSchema,
    ) -> AbstractStructuredType | None:
        """
        Build a typed structured-type instance from a single ``rdf:li``
        element. Mirrors upstream ``parseLiElement`` for the simple
        attribute-only / nested-rdf:Description forms used by
        Photoshop-style typed arrays.

        Attribute-form (PDFBOX-3882):
        ``<rdf:li photoshop:LayerName="..." photoshop:LayerText="..."/>``
        — each non-RDF / non-XML attribute populates the matching field
        on the structured-type instance.

        Element-form: a nested ``rdf:Description`` (or bare element-form
        fields) — same as upstream's ``parseLiDescription``: each child
        element whose local-name is a known field is set on the instance.
        """
        instance = element_cls(schema.get_metadata())
        field_types = getattr(element_cls, "_FIELD_TYPES", {})

        # Attribute-form fields.
        for qname, value in li.attrib.items():
            attr_ns, attr_local = _strip_qname(qname)
            if attr_ns in (_RDF_NS, _XML_NS):
                continue
            if attr_local in field_types:
                instance.add_simple_property(attr_local, value)

        # Element-form fields. Honor a nested ``rdf:Description`` wrapper
        # (PDFBOX-6126) — fall through to its children, also picking up
        # the wrapper's attribute-form fields.
        children = list(li)
        if len(children) == 1:
            inner_ns, inner_local = _strip_qname(children[0].tag)
            if inner_ns == _RDF_NS and inner_local == "Description":
                description = children[0]
                for qname, value in description.attrib.items():
                    attr_ns, attr_local = _strip_qname(qname)
                    if attr_ns in (_RDF_NS, _XML_NS):
                        continue
                    if attr_local in field_types:
                        instance.add_simple_property(attr_local, value)
                children = list(description)
        for child in children:
            child_ns, child_local = _strip_qname(child.tag)
            if child_ns == _RDF_NS:
                continue
            if child_local in field_types:
                text = (child.text or "").strip()
                instance.add_simple_property(child_local, text)

        return instance

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

    # ------------------------------------------------------------------
    # Upstream-named helpers (snake_case ports of DomXmpParser private
    # methods). These mirror the upstream method surface so callers and
    # ports of upstream tests can reach the same semantic hooks. They
    # delegate to existing private helpers where possible and add the
    # strict / lenient validation logic that upstream concentrates in
    # these helpers.
    # ------------------------------------------------------------------

    @staticmethod
    def is_schema_extension_property(element: ET.Element | None) -> bool:
        """Mirror of upstream ``isSchemaExtensionProperty`` (line 261).

        Returns True if the element's prefix is ``pdfaExtension``. ElementTree
        does not retain element prefixes, so we instead check the namespace URI
        of the PDF/A extension namespace.
        """
        if element is None:
            return False
        ns, _local = _strip_qname(element.tag)
        return ns == "http://www.aiim.org/pdfa/ns/extension/"

    def expect_naming(
        self,
        element: ET.Element,
        ns: str | None,
        prefix: str | None,  # noqa: ARG002 - prefix info dropped by ElementTree
        local_name: str | None,
    ) -> None:
        """Mirror of upstream ``expectNaming`` (line 996).

        Validates that the element matches the expected namespace, prefix, and
        local name. Raises :class:`XmpParsingException` (FORMAT) on mismatch.
        ElementTree does not preserve prefixes on Element nodes, so the
        ``prefix`` argument is accepted for upstream-API parity but only the
        namespace and local name are enforced here.
        """
        actual_ns, actual_local = _strip_qname(element.tag)
        if ns is not None and ns != actual_ns:
            raise XmpParsingException(
                XmpParsingException.ErrorType.FORMAT,
                f"Expecting namespace '{ns}' and found '{actual_ns}'",
            )
        if local_name is not None and local_name != actual_local:
            raise XmpParsingException(
                XmpParsingException.ErrorType.FORMAT,
                f"Expecting local name '{local_name}' and found '{actual_local}'",
            )

    def find_descriptions_parent(self, root: ET.Element) -> ET.Element:
        """Mirror of upstream ``findDescriptionsParent`` (line 949).

        Locates the ``rdf:RDF`` element. If ``root`` is already
        ``rdf:RDF`` it is returned; otherwise it must be ``x:xmpmeta``
        (or ``x:xapmeta`` in lenient mode) wrapping a single ``rdf:RDF``
        child.
        """
        ns, local = _strip_qname(root.tag)
        if ns == _RDF_NS and local == "RDF":
            return root
        # x:xmpmeta wrapper
        wrapper_ns = "adobe:ns:meta/"
        if not self._strict_parsing and local == "xapmeta":
            self.expect_naming(root, wrapper_ns, "x", "xapmeta")
        else:
            self.expect_naming(root, wrapper_ns, "x", "xmpmeta")
        children = [c for c in root if isinstance(c.tag, str)]
        if not children:
            raise XmpParsingException(
                XmpParsingException.ErrorType.FORMAT,
                "No rdf description found in xmp",
            )
        if len(children) > 1:
            raise XmpParsingException(
                XmpParsingException.ErrorType.FORMAT,
                "More than one element found in x:xmpmeta",
            )
        rdf = children[0]
        self.expect_naming(rdf, _RDF_NS, "rdf", "RDF")
        return rdf

    @staticmethod
    def remove_comments_and_blanks(root: ET.Element) -> None:
        """Mirror of upstream ``removeCommentsAndBlanks`` (line 1020).

        ElementTree by default drops XML comments and trims surrounding
        whitespace itself, so this is mostly a no-op kept for upstream-API
        parity. Any text-only-whitespace siblings are normalised to ``None``
        so downstream walkers that look at ``Element.text`` or ``.tail``
        observe the same shape upstream produces after the cleanup pass.
        """
        for elem in root.iter():
            if elem.text is not None and not elem.text.strip():
                elem.text = None
            if elem.tail is not None and not elem.tail.strip():
                elem.tail = None

    def parse_initial_xpacket(self, data: str) -> dict[str, str | None]:
        """Mirror of upstream ``parseInitialXpacket`` (line 864).

        Tokenises the inner data of the leading ``<?xpacket ...?>``
        processing instruction. Recognises ``begin``, ``id``, ``bytes``,
        ``encoding``; rejects unknown attributes. Returns a dict suitable
        for :meth:`XMPMetadata.create_xmp_metadata`.

        Raises :class:`XmpParsingException` with
        :attr:`XmpParsingException.ErrorType.XPACKET_BAD_START` for malformed
        attribute syntax or unrecognised attribute names.
        """
        result: dict[str, str | None] = {
            "begin": None,
            "id": None,
            "bytes": None,
            "encoding": None,
        }
        for token in data.split():
            if not token.endswith('"') and not token.endswith("'"):
                raise XmpParsingException(
                    XmpParsingException.ErrorType.XPACKET_BAD_START,
                    f"Cannot understand PI data part : '{token}' in '{data}'",
                )
            quote = token[-1]
            pos = token.find(f"={quote}")
            if pos <= 0:
                raise XmpParsingException(
                    XmpParsingException.ErrorType.XPACKET_BAD_START,
                    f"Cannot understand PI data part : '{token}' in '{data}'",
                )
            name = token[:pos]
            if len(token) - 1 < pos + 2:
                raise XmpParsingException(
                    XmpParsingException.ErrorType.XPACKET_BAD_START,
                    f"Cannot understand PI data part : '{token}' in '{data}'",
                )
            value = token[pos + 2 : -1]
            if name not in result:
                raise XmpParsingException(
                    XmpParsingException.ErrorType.XPACKET_BAD_START,
                    f"Unknown attribute in xpacket PI : '{token}'",
                )
            result[name] = value
        return result

    def parse_end_packet(self, data: str) -> str:
        """Mirror of upstream ``parseEndPacket`` (line 921).

        Validates the trailing ``<?xpacket end='r|w'?>`` processing
        instruction and returns the single-character marker. Raises
        :class:`XmpParsingException` (XPACKET_BAD_END) on malformed input.
        """
        if not data.startswith("end="):
            raise XmpParsingException(
                XmpParsingException.ErrorType.XPACKET_BAD_END,
                "Expected xpacket 'end' attribute (must be present and placed in first)",
            )
        if len(data) <= 5:
            raise XmpParsingException(
                XmpParsingException.ErrorType.XPACKET_BAD_END,
                "Expected xpacket 'end' attribute (must be present and placed in first)",
            )
        end_char = data[5]
        if end_char not in ("r", "w"):
            raise XmpParsingException(
                XmpParsingException.ErrorType.XPACKET_BAD_END,
                "Expected xpacket 'end' attribute with value 'r' or 'w' ",
            )
        return end_char

    def maybe_add_non_standard_namespace(
        self,
        metadata: XMPMetadata,  # noqa: ARG002 - placeholder for TypeMapping integration
        prefix: str,
        namespace: str,
    ) -> None:
        """Mirror of upstream ``maybeAddNonStandardNamespace`` (line 244).

        Upstream registers non-standard namespaces with ``TypeMapping`` so
        unknown schemas survive a parse / re-serialise round-trip. pypdfbox
        currently records the mapping on the parser instance for visibility
        until the full ``TypeMapping`` port lands; the existing
        ``_collect_namespace_prefixes`` path already preserves prefixes for
        unknown namespaces.
        """
        if namespace == _RDF_NS:
            return
        if not hasattr(self, "_non_standard_namespaces"):
            self._non_standard_namespaces: dict[str, str] = {}
        self._non_standard_namespaces[prefix] = namespace

    def load_attributes(self, schema: XMPSchema, element: ET.Element) -> None:
        """Mirror of upstream ``loadAttributes`` (line 721).

        Copies ``rdf:about`` and ``xml:*`` qualifiers from ``element`` onto
        ``schema``. Other attributes are left to the regular property-walk
        path (handled by :meth:`_merge_description`).
        """
        for qname, value in element.attrib.items():
            ns, local = _strip_qname(qname)
            if ns == _RDF_NS and local == "about":
                schema.set_about(value)
            elif ns == _XML_NS:
                # xml:lang and friends round-trip as namespace-bound attributes
                schema._namespaces.setdefault(local, value)

    def check_property_definition(
        self,
        schema: XMPSchema,
        ns: str,
        local: str,
    ) -> None:
        """Mirror of upstream ``checkPropertyDefinition`` (line 1084).

        Strict mode: raises :class:`XmpParsingException` (INVALID_TYPE) when
        ``local`` is not in the schema's ``KNOWN_PROPERTIES`` allow-list.
        Lenient mode: no-op (caller falls back to a Text type).
        """
        self._validate_strict_property(schema, ns, local)

    def create_property(
        self,
        metadata: XMPMetadata,
        element: ET.Element,
        schema: XMPSchema,
    ) -> None:
        """Mirror of upstream ``createProperty`` (line 436).

        Dispatches an element to the correct ``manage_*`` helper based on
        its inferred shape. pypdfbox stores properties as plain Python
        primitives at this layer, so ``manage_simple_type`` /
        ``manage_array`` / ``manage_lang_alt`` collapse into the existing
        ``_assign`` path.
        """
        ns, local = _strip_qname(element.tag)
        del metadata, ns  # unused: schema already knows its namespace
        parsed_value = self._parse_property_value(element)
        self._assign(schema, local, parsed_value)

    def manage_simple_type(self, schema: XMPSchema, local: str, value: str) -> None:
        """Mirror of upstream ``manageSimpleType`` (line 557)."""
        schema.set_text_property_value(local, value)

    def manage_array(self, schema: XMPSchema, local: str, items: list[str]) -> None:
        """Mirror of upstream ``manageArray`` (line 569)."""
        for item in items:
            schema.add_qualified_bag_value(local, item)

    def manage_lang_alt(
        self, schema: XMPSchema, local: str, lang_map: dict[str, str]
    ) -> None:
        """Mirror of upstream ``manageLangAlt`` (line 628)."""
        for lang, v in lang_map.items():
            schema.set_unqualified_language_property_value(local, lang, v)

    def manage_structured_type(
        self,
        schema: XMPSchema,  # noqa: ARG002 - rich-type system not yet ported
        local: str,  # noqa: ARG002
        element: ET.Element,  # noqa: ARG002
    ) -> None:
        """Mirror of upstream ``manageStructuredType`` (line 520).

        Rich structured types (``DimensionsType``, ``ResourceEventType``,
        etc.) are not yet ported; this is a placeholder so callers can hook
        the same surface name when the type system lands.
        """
        return None

    def manage_defined_type(
        self,
        schema: XMPSchema,  # noqa: ARG002
        local: str,  # noqa: ARG002
        element: ET.Element,  # noqa: ARG002
    ) -> None:
        """Mirror of upstream ``manageDefinedType`` (line 487).

        Defined types (extension-schema-declared structured properties)
        require the ``TypeMapping`` infrastructure that has not yet been
        ported.
        """
        return None

    def parse_description_root(
        self,
        metadata: XMPMetadata,
        description: ET.Element,
        per_ns: dict[str, XMPSchema] | None = None,
        namespace_prefixes: dict[str, str] | None = None,
    ) -> dict[str, XMPSchema]:
        """Mirror of upstream ``parseDescriptionRoot`` (line 305)."""
        if per_ns is None:
            per_ns = {}
        if namespace_prefixes is None:
            namespace_prefixes = {}
        self._merge_description(description, metadata, per_ns, namespace_prefixes)
        return per_ns

    def parse_description_root_attr(
        self,
        metadata: XMPMetadata,
        description: ET.Element,
        attr_qname: str,
        attr_value: str,
        per_ns: dict[str, XMPSchema],
        namespace_prefixes: dict[str, str] | None = None,
    ) -> None:
        """Mirror of upstream ``parseDescriptionRootAttr`` (line 346).

        Resolves the schema for the attribute's namespace and stores the
        attribute's value as a simple text property on that schema.
        """
        if namespace_prefixes is None:
            namespace_prefixes = {}
        ns, local = _strip_qname(attr_qname)
        if ns in ("", _RDF_NS, _XML_NS):
            return
        about = description.get(f"{{{_RDF_NS}}}about", "")
        schema = self._schema_for(
            ns, local, description, metadata, per_ns, about, namespace_prefixes
        )
        self._validate_strict_property(schema, ns, local)
        schema.set_text_property_value(local, attr_value)

    def parse_children_as_properties(
        self,
        metadata: XMPMetadata,
        description: ET.Element,
        per_ns: dict[str, XMPSchema],
        namespace_prefixes: dict[str, str] | None = None,
    ) -> None:
        """Mirror of upstream ``parseChildrenAsProperties`` (line 404)."""
        if namespace_prefixes is None:
            namespace_prefixes = {}
        about = description.get(f"{{{_RDF_NS}}}about", "")
        for child in description:
            ns, local = _strip_qname(child.tag)
            if ns == _RDF_NS:
                continue
            schema = self._schema_for(
                ns, local, description, metadata, per_ns, about, namespace_prefixes
            )
            self._validate_strict_property(schema, ns, local)
            parsed_value = self._parse_property_value(child)
            self._assign(schema, local, parsed_value)

    def parse_schema_extensions(
        self,
        metadata: XMPMetadata,  # noqa: ARG002 - PDF/A extension type system not ported
        description: ET.Element,
    ) -> list[ET.Element]:
        """Mirror of upstream ``parseSchemaExtensions`` (line 266).

        Returns the list of ``pdfaExtension:*`` child elements so callers
        can inspect them. Full extension-schema construction depends on
        ``PdfaExtensionHelper`` which is out of scope for this cluster.
        """
        return [
            child
            for child in description
            if self.is_schema_extension_property(child)
        ]

    def parse_description_inner(
        self,
        metadata: XMPMetadata,  # noqa: ARG002
        description: ET.Element,  # noqa: ARG002
    ) -> None:
        """Mirror of upstream ``parseDescriptionInner`` (line 634).

        Inner-description parsing depends on ``TypeMapping`` /
        ``PropertiesDescription`` which are part of the rich type system
        that hasn't been ported yet.
        """
        return None

    def parse_li_element(
        self,
        metadata: XMPMetadata,  # noqa: ARG002
        descriptor: tuple[str, str],  # noqa: ARG002 - (ns, local)
        li_element: ET.Element,
    ) -> object:
        """Mirror of upstream ``parseLiElement`` (line 657).

        Returns the simple text content of an ``rdf:li`` element. Structured
        ``rdf:li`` items (``rdf:parseType="Resource"``) require the typed
        property system and are returned as-is.
        """
        if not list(li_element):
            return (li_element.text or "").strip()
        # Structured li: surface raw element until rich-type port lands.
        return li_element

    def parse_li_description(
        self,
        metadata: XMPMetadata,  # noqa: ARG002
        parent_descriptor: tuple[str, str],  # noqa: ARG002
        li_description_element: ET.Element,  # noqa: ARG002
    ) -> None:
        """Mirror of upstream ``parseLiDescription`` (line 751).

        Builds an ``AbstractStructuredType`` from an ``rdf:li`` /
        ``rdf:Description`` pair. Depends on the typed-property system not
        yet ported in this cluster.
        """
        return None

    def instanciate_structured(
        self,
        type_name: str,  # noqa: ARG002
        name: str,  # noqa: ARG002
        structured_namespace: str | None = None,  # noqa: ARG002
    ) -> None:
        """Mirror of upstream ``instanciateStructured`` (line 1060).

        Note the upstream Java spelling (``instanciate`` rather than
        ``instantiate``) is preserved for parity. Returns ``None`` until
        the structured type infrastructure is ported.
        """
        return None

    def try_parse_attributes_as_properties(
        self,
        metadata: XMPMetadata,
        li_element: ET.Element,
        per_ns: dict[str, XMPSchema] | None = None,
        namespace_prefixes: dict[str, str] | None = None,
    ) -> dict[str, XMPSchema]:
        """Mirror of upstream ``tryParseAttributesAsProperties`` (line 1124).

        Walks the attributes of an ``rdf:li`` (or ``rdf:Description``) and
        treats each non-RDF / non-XML attribute as a simple text property
        on the schema for its namespace. Mirrors PDFBOX-3882.
        """
        if per_ns is None:
            per_ns = {}
        if namespace_prefixes is None:
            namespace_prefixes = {}
        about = li_element.get(f"{{{_RDF_NS}}}about", "")
        for qname, value in li_element.attrib.items():
            ns, local = _strip_qname(qname)
            if ns in ("", _RDF_NS, _XML_NS):
                continue
            schema = self._schema_for(
                ns, local, li_element, metadata, per_ns, about, namespace_prefixes
            )
            self._validate_strict_property(schema, ns, local)
            schema.set_text_property_value(local, value)
        return per_ns


# Convenience module-level wrapper to mirror upstream usage patterns.
def parse(source: bytes | bytearray | memoryview | str | IO[bytes]) -> XMPMetadata:
    return DomXmpParser().parse(source)


__all__ = ["DomXmpParser", "XmpParsingException", "parse"]

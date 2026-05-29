"""DOM serialiser for :class:`XMPMetadata`.

Mirrors ``org.apache.xmpbox.xml.XmpSerializer`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/xml/XmpSerializer.java``).

The upstream class produces an ``rdf:RDF`` tree wrapped in ``xpacket``
processing instructions and writes it via a ``Transformer``. We rebuild
the same tree with :mod:`xml.dom.minidom`, then call
``writexml``/``toprettyxml`` for the final byte stream.
"""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from typing import BinaryIO
from xml.dom.minidom import Document, Element

from pypdfbox.xmpbox.type.abstract_complex_property import AbstractComplexProperty
from pypdfbox.xmpbox.type.abstract_field import AbstractField
from pypdfbox.xmpbox.type.abstract_simple_property import AbstractSimpleProperty
from pypdfbox.xmpbox.type.abstract_structured_type import AbstractStructuredType
from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
from pypdfbox.xmpbox.type.boolean_type import BooleanType
from pypdfbox.xmpbox.type.date_type import DateType
from pypdfbox.xmpbox.type.integer_type import IntegerType
from pypdfbox.xmpbox.type.lang_alt import LangAlt
from pypdfbox.xmpbox.type.text_type import TextType
from pypdfbox.xmpbox.xml.xmp_serialization_exception import XmpSerializationException
from pypdfbox.xmpbox.xmp_metadata import (
    DEFAULT_RDF_PREFIX,
    DESCRIPTION_NAME,
    RDF_NAMESPACE,
    XMPMetadata,
)

_XMLNS_NS = "http://www.w3.org/2000/xmlns/"


class XmpSerializer:
    """Write an :class:`XMPMetadata` document as XML/RDF bytes."""

    def __init__(self) -> None:
        self._rdf: Element | None = None

    # ------------------------------------------------------------------
    def serialize(
        self,
        metadata: XMPMetadata,
        output: BinaryIO,
        with_xpacket: bool = True,
    ) -> None:
        """Write ``metadata`` as XML/RDF to ``output``."""
        doc = Document()
        self._rdf = self._create_rdf_element(doc, metadata, with_xpacket)
        for schema in metadata.get_all_schemas():
            self._rdf.appendChild(self.serialize_schema(doc, schema))
        self._save(doc, output)

    def serialize_schema(self, doc: Document, schema) -> Element:
        """Build a ``rdf:Description`` element for ``schema``."""
        selem = doc.createElementNS(RDF_NAMESPACE, f"{DEFAULT_RDF_PREFIX}:{DESCRIPTION_NAME}")
        about = schema.get_about_value() if hasattr(schema, "get_about_value") else ""
        selem.setAttributeNS(RDF_NAMESPACE, f"{DEFAULT_RDF_PREFIX}:about", about or "")
        prefix = schema.get_prefix() if hasattr(schema, "get_prefix") else None
        ns = schema.get_namespace() if hasattr(schema, "get_namespace") else None
        if prefix and ns:
            selem.setAttributeNS(_XMLNS_NS, f"xmlns:{prefix}", ns)
        self._fill_element_with_attributes(selem, schema)
        raw_fields = (
            schema.get_all_properties() if hasattr(schema, "get_all_properties") else []
        )
        fields = self._normalize_schema_fields(schema, raw_fields)
        self.serialize_fields(doc, selem, fields, prefix or "", None, True)
        return selem

    # ------------------------------------------------------------------
    def _normalize_schema_fields(
        self, schema, raw_fields,
    ) -> list[AbstractField]:
        """Coerce a schema's ``get_all_properties()`` payload into a list
        of :class:`AbstractField` ready for serialization.

        ``AbstractComplexProperty`` subclasses already return an iterable
        of ``AbstractField``; ``XMPSchema`` subclasses (Dublin Core,
        Photoshop, etc.) return a flat ``dict[str, primitive]`` because
        they store property values in Python primitive form. For the
        latter, prefer typed-cache wrappers on the schema when present;
        otherwise wrap primitives heuristically (``str`` → TextType,
        ``int`` → IntegerType, ``list`` → Bag, ``dict`` → LangAlt, etc.).
        """
        if isinstance(raw_fields, dict):
            return list(self._iter_flat_typed(schema, raw_fields))
        return list(raw_fields) if raw_fields else []

    def _iter_flat_typed(self, schema, raw_dict):
        metadata = getattr(schema, "_metadata", None) or getattr(
            schema, "metadata", None
        )
        ns = schema.get_namespace() if hasattr(schema, "get_namespace") else None
        prefix = schema.get_prefix() if hasattr(schema, "get_prefix") else None
        cached = getattr(schema, "_typed_properties", None) or {}
        for name, value in raw_dict.items():
            wrapped = cached.get(name)
            if isinstance(wrapped, AbstractField):
                yield wrapped
                continue
            field = self._wrap_primitive(
                metadata, ns, prefix, name, value, schema=schema,
            )
            if field is not None:
                yield field

    def _wrap_primitive(
        self,
        metadata, ns: str | None, prefix: str | None, name: str, value: object,
        *,
        schema=None,
    ) -> AbstractField | None:
        """Heuristic primitive → AbstractField wrap for the flat-dict
        schema-storage layout. Returns ``None`` for value shapes the
        wrapper doesn't recognize (caller skips silently)."""
        # Wave 1370: schemas may also store an already-typed ``AbstractField``
        # directly in ``_properties`` (e.g. ``XMPMediaManagementSchema.set_derived_from``
        # installs a ``ResourceRefType`` under ``DerivedFrom``). Yield those
        # untouched — previously the wrapper fell through to ``return None``
        # and the property was silently dropped from the serialised packet.
        if isinstance(value, AbstractField):
            if not value.get_property_name():
                value.set_property_name(name)
            return value
        # ``bool`` must be checked before ``int`` (Python bool subclasses int).
        if isinstance(value, bool):
            return BooleanType(metadata, ns, prefix, name, value)
        if isinstance(value, int):
            return IntegerType(metadata, ns, prefix, name, value)
        if isinstance(value, datetime):
            return DateType(metadata, ns, prefix, name, value)
        if isinstance(value, str):
            return TextType(metadata, ns, prefix, name, value)
        if isinstance(value, list):
            cardinality = self._cardinality_hint(schema, name) or Cardinality.Bag
            arr = ArrayProperty(metadata, ns, prefix, name, cardinality)
            for item in value:
                if isinstance(item, str):
                    arr.add_property(TextType(metadata, ns, prefix, name, item))
            return arr
        if isinstance(value, dict):
            la = LangAlt(metadata, ns, prefix, name)
            for lang, text in value.items():
                if isinstance(text, str):
                    la.set_language_value(lang, text)
            return la
        return None

    @staticmethod
    def _cardinality_hint(schema, name: str) -> Cardinality | None:
        """Schemas may declare per-field cardinality overrides via either a
        class-level ``_FIELD_CARDINALITIES`` mapping or a
        ``get_property_cardinality(name)`` method. Used by
        :meth:`_wrap_primitive` to render lists as Seq/Alt instead of the
        default Bag where the schema knows better.
        """
        if schema is None:
            return None
        getter = getattr(schema, "get_property_cardinality", None)
        if callable(getter):
            try:
                hint = getter(name)
            except Exception:
                hint = None
            if isinstance(hint, Cardinality):
                return hint
        mapping = getattr(schema, "_FIELD_CARDINALITIES", None)
        if isinstance(mapping, dict):
            hint = mapping.get(name)
            if isinstance(hint, Cardinality):
                return hint
        return None

    def serialize_fields(
        self,
        doc: Document,
        parent: Element,
        fields: list[AbstractField],
        resource_ns: str,
        prefix: str | None,
        wrap_with_property: bool,
    ) -> None:
        """Append serialised ``fields`` to ``parent``."""
        for field in fields:
            self._append_field(doc, parent, field, resource_ns, prefix)

    # ------------------------------------------------------------------
    def _append_field(
        self,
        doc: Document,
        parent: Element,
        field: AbstractField,
        resource_ns: str,
        prefix: str | None,
    ) -> None:
        # Belt-and-suspenders: ``serialize_schema`` already converts flat-dict
        # schema entries to AbstractField via ``_normalize_schema_fields``,
        # but callers that invoke ``serialize_fields`` directly may still
        # hand us a raw primitive. Skip rather than crash.
        if not isinstance(field, AbstractField):
            return
        prop_name = field.get_property_name() or "value"
        prefix_to_use = field.get_prefix() if hasattr(field, "get_prefix") else None
        ns_uri = field.get_namespace() if hasattr(field, "get_namespace") else None
        tag = (
            f"{prefix_to_use}:{prop_name}" if prefix_to_use else prop_name
        )
        elem = doc.createElementNS(ns_uri or "", tag) if ns_uri else doc.createElement(tag)
        if isinstance(field, AbstractSimpleProperty):
            if hasattr(field, "get_string_value"):
                value = field.get_string_value()
            else:
                value = field.get_raw_value()
            text = doc.createTextNode(value if value is not None else "")
            elem.appendChild(text)
        elif isinstance(field, ArrayProperty):
            if hasattr(field, "get_array_type"):
                array_type = field.get_array_type()
                tag_value = (
                    array_type.value if hasattr(array_type, "value") else array_type
                )
                list_tag = f"{DEFAULT_RDF_PREFIX}:{tag_value}"
            else:
                list_tag = f"{DEFAULT_RDF_PREFIX}:Bag"
            list_elem = doc.createElementNS(RDF_NAMESPACE, list_tag)
            for child in field.get_all_properties():
                li = doc.createElementNS(RDF_NAMESPACE, f"{DEFAULT_RDF_PREFIX}:li")
                # Propagate child attributes (xml:lang for LangAlt entries,
                # custom qualifiers, etc.) before adding text content.
                self._fill_element_with_attributes(li, child)
                if isinstance(child, AbstractSimpleProperty):
                    li.appendChild(
                        doc.createTextNode(
                            child.get_string_value() if hasattr(child, "get_string_value") else ""
                        )
                    )
                elif isinstance(child, (AbstractComplexProperty, AbstractStructuredType)):
                    sub_fields = (
                        child.get_all_properties()
                        if hasattr(child, "get_all_properties")
                        else []
                    )
                    self.serialize_fields(doc, li, sub_fields, resource_ns, None, True)
                list_elem.appendChild(li)
            elem.appendChild(list_elem)
        elif isinstance(field, (AbstractComplexProperty, AbstractStructuredType)):
            sub_fields = (
                field.get_all_properties()
                if hasattr(field, "get_all_properties")
                else []
            )
            self.serialize_fields(doc, elem, sub_fields, resource_ns, None, True)
        parent.appendChild(elem)

    def _fill_element_with_attributes(self, elem: Element, owner) -> None:
        if not hasattr(owner, "get_all_attributes"):
            return
        try:
            attributes = owner.get_all_attributes()
        except Exception:  # pragma: no cover
            return
        for attr in attributes or []:
            ns = getattr(attr, "get_namespace", lambda: None)()
            name = getattr(attr, "get_name", lambda: None)()
            value = getattr(attr, "get_value", lambda: "")()
            if name is None:
                continue
            if ns:
                elem.setAttributeNS(ns, name, value or "")
            else:
                elem.setAttribute(name, value or "")

    def _create_rdf_element(
        self, doc: Document, metadata: XMPMetadata, with_xpacket: bool
    ) -> Element:
        if with_xpacket:
            begin = metadata.get_xpacket_begin() or "﻿"
            xpacket_id = metadata.get_xpacket_id() or "W5M0MpCehiHzreSzNTczkc9d"
            doc.appendChild(
                doc.createProcessingInstruction(
                    "xpacket", f'begin="{begin}" id="{xpacket_id}"'
                )
            )
        xmpmeta = doc.createElementNS("adobe:ns:meta/", "x:xmpmeta")
        xmpmeta.setAttributeNS(_XMLNS_NS, "xmlns:x", "adobe:ns:meta/")
        doc.appendChild(xmpmeta)
        rdf = doc.createElementNS(RDF_NAMESPACE, f"{DEFAULT_RDF_PREFIX}:RDF")
        rdf.setAttributeNS(_XMLNS_NS, f"xmlns:{DEFAULT_RDF_PREFIX}", RDF_NAMESPACE)
        xmpmeta.appendChild(rdf)
        if with_xpacket:
            end_marker = metadata.get_end_xpacket() or "w"
            doc.appendChild(
                doc.createProcessingInstruction("xpacket", f'end="{end_marker}"')
            )
        return rdf

    def _save(self, doc: Document, output: BinaryIO) -> None:
        self.save(doc, output)

    # --- Upstream parity surface --------------------------------------
    # These map upstream's protected/private helpers onto public methods
    # so callers (and the parity scanner) can see them.

    def create_rdf_element(
        self, doc: Document, metadata: XMPMetadata, with_xpacket: bool
    ) -> Element:
        """Mirror of ``XmpSerializer.createRdfElement`` (Java line 271)."""
        return self._create_rdf_element(doc, metadata, with_xpacket)

    def fill_element_with_attributes(self, elem: Element, owner: object) -> None:
        """Mirror of ``XmpSerializer.fillElementWithAttributes`` (Java line 214)."""
        self._fill_element_with_attributes(elem, owner)

    def normalize_attributes(self, prop: object) -> list[object]:
        """Mirror of ``XmpSerializer.normalizeAttributes`` (Java line 243).

        Returns the property's attributes in the order they should appear
        on the serialised element.
        """
        if not hasattr(prop, "get_all_attributes"):
            return []
        try:
            return list(prop.get_all_attributes() or [])
        except Exception:  # pragma: no cover
            return []

    def save(self, doc: Document, output: BinaryIO, encoding: str = "UTF-8") -> None:
        """Mirror of ``XmpSerializer.save`` (Java line 308).

        Upstream declares ``throws TransformerException``; any failure while
        rendering the DOM or writing it to the stream is reported as an
        :class:`XmpSerializationException` (matching the serializer's
        documented error contract).

        Upstream sets ``OMIT_XML_DECLARATION="yes"`` on the Transformer, so the
        serialized packet starts with the ``<?xpacket?>`` processing
        instruction and never with an ``<?xml version=...?>`` prolog — an XMP
        packet that begins with an XML declaration is malformed. ``minidom``'s
        ``Document.toxml`` always prepends that prolog, so we render each
        top-level node individually with ``writexml`` (which never emits the
        prolog) to match upstream byte-for-byte at the packet boundary.
        """
        try:
            buf = StringIO()
            for node in doc.childNodes:
                node.writexml(buf, "", "", "")
            output.write(buf.getvalue().encode(encoding))
        except (OSError, ValueError, TypeError) as exc:
            raise XmpSerializationException(
                "Failed to serialize the XMP metadata", exc
            ) from exc


__all__ = ["XmpSerializer"]

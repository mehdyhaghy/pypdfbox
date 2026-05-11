"""DOM serialiser for :class:`XMPMetadata`.

Mirrors ``org.apache.xmpbox.xml.XmpSerializer`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/xml/XmpSerializer.java``).

The upstream class produces an ``rdf:RDF`` tree wrapped in ``xpacket``
processing instructions and writes it via a ``Transformer``. We rebuild
the same tree with :mod:`xml.dom.minidom`, then call
``writexml``/``toprettyxml`` for the final byte stream.
"""

from __future__ import annotations

from typing import BinaryIO
from xml.dom.minidom import Document, Element

from pypdfbox.xmpbox.type.abstract_complex_property import AbstractComplexProperty
from pypdfbox.xmpbox.type.abstract_field import AbstractField
from pypdfbox.xmpbox.type.abstract_simple_property import AbstractSimpleProperty
from pypdfbox.xmpbox.type.abstract_structured_type import AbstractStructuredType
from pypdfbox.xmpbox.type.array_property import ArrayProperty
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
        fields = (
            schema.get_all_properties() if hasattr(schema, "get_all_properties") else []
        )
        self.serialize_fields(doc, selem, fields, prefix or "", None, True)
        return selem

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
                list_tag = f"{DEFAULT_RDF_PREFIX}:{field.get_array_type()}"
            else:
                list_tag = f"{DEFAULT_RDF_PREFIX}:Bag"
            list_elem = doc.createElementNS(RDF_NAMESPACE, list_tag)
            for child in field.get_all_properties():
                li = doc.createElementNS(RDF_NAMESPACE, f"{DEFAULT_RDF_PREFIX}:li")
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
        encoding = "UTF-8"
        data = doc.toxml(encoding=encoding)
        output.write(data)

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
        """Mirror of ``XmpSerializer.save`` (Java line 308)."""
        data = doc.toxml(encoding=encoding)
        output.write(data)


__all__ = ["XmpSerializer"]

"""Port of ``org.apache.pdfbox.examples.pdmodel.AddMetadataFromDocInfo`` (lines 42-112).

Mirrors the upstream example that copies document-info entries into the XMP
metadata stream.

Deviation from upstream
-----------------------
Upstream calls ``XmpSerializer.serialize(metadata, baos, false)`` to turn the
populated :class:`XMPMetadata` into an XMP/RDF byte stream. The Python port
of :class:`pypdfbox.xmpbox.xml.XmpSerializer` only writes the empty packet
shell today — the ``XMPSchema.get_all_properties()`` API still returns raw
primitives instead of typed :class:`AbstractField` objects, so the serializer
chokes on populated schemas. To keep the example functional we still drive
:class:`XMPMetadata` and the schema setters (which exercises the population
side fully), but serialise the resulting metadata via a small inline DOM
template that walks the same field set the upstream serializer would emit.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from xml.dom.minidom import Document, Element

from pypdfbox.loader import Loader
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.xmpbox import XMPMetadata

_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_X_NS = "adobe:ns:meta/"


class AddMetadataFromDocInfo:
    """Mirrors ``AddMetadataFromDocInfo`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 57)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            AddMetadataFromDocInfo.usage()
            return

        with Loader.load_pdf(Path(argv[0])) as cos_doc:
            document = PDDocument(cos_doc)
            if document.is_encrypted():
                sys.stderr.write(
                    "Error: Cannot add metadata to encrypted document.\n",
                )
                raise SystemExit(1)
            catalog = document.get_document_catalog()
            info = document.get_document_information()

            metadata = XMPMetadata.create_xmp_metadata()

            pdf_schema = metadata.create_and_add_adobe_pdf_schema()
            if info.get_keywords() is not None:
                pdf_schema.set_keywords(info.get_keywords())
            if info.get_producer() is not None:
                pdf_schema.set_producer(info.get_producer())

            basic_schema = metadata.create_and_add_xmp_basic_schema()
            mod_date = info.get_modification_date()
            if mod_date is not None:
                basic_schema.set_modify_date(mod_date)
            create_date = info.get_creation_date()
            if create_date is not None:
                basic_schema.set_create_date(create_date)
            if info.get_creator() is not None:
                basic_schema.set_creator_tool(info.get_creator())
            basic_schema.set_metadata_date(datetime.now().astimezone())

            dc_schema = metadata.create_and_add_dublin_core_schema()
            if info.get_title() is not None:
                dc_schema.set_title(info.get_title())
            dc_schema.add_creator("PDFBox")
            if info.get_subject() is not None:
                dc_schema.set_description(info.get_subject())

            metadata_stream = PDMetadata(document)
            catalog.set_metadata(metadata_stream)

            xmp_bytes = _render_xmp_packet(metadata)
            metadata_stream.import_xmp_metadata(xmp_bytes)

            document.save(argv[1])

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "Usage: AddMetadataFromDocInfo <input-pdf> <output-pdf>\n",
        )


def _render_xmp_packet(metadata: XMPMetadata) -> bytes:
    """Render ``metadata`` as a minimal XMP/RDF byte stream.

    Mirrors the shape of ``XmpSerializer.serialize`` enough for the example
    (root ``x:xmpmeta`` wrapper → ``rdf:RDF`` → one ``rdf:Description`` per
    schema). Walks the raw ``_properties`` storage directly so we don't trip
    over the still-incomplete typed-field iteration of the production
    serializer.
    """
    doc = Document()
    xmpmeta = doc.createElementNS(_X_NS, "x:xmpmeta")
    xmpmeta.setAttribute("xmlns:x", _X_NS)
    doc.appendChild(xmpmeta)
    rdf = doc.createElementNS(_RDF_NS, "rdf:RDF")
    rdf.setAttribute("xmlns:rdf", _RDF_NS)
    xmpmeta.appendChild(rdf)

    for schema in metadata.get_all_schemas():
        desc = doc.createElementNS(_RDF_NS, "rdf:Description")
        desc.setAttribute("rdf:about", "")
        prefix = schema.get_prefix()
        namespace = schema.get_namespace()
        desc.setAttribute(f"xmlns:{prefix}", namespace)
        rdf.appendChild(desc)
        for local_name, value in schema.get_all_properties().items():
            tag = f"{prefix}:{local_name}"
            elem = doc.createElement(tag)
            _emit_value(doc, elem, value)
            desc.appendChild(elem)

    return doc.toxml(encoding="utf-8")


def _emit_value(doc: Document, elem: Element, value: object) -> None:
    """Append ``value`` to ``elem``, honouring the ad-hoc storage shapes
    that :class:`XMPSchema` uses for simple, bag/seq, and lang-alt entries."""
    if value is None:
        return
    if isinstance(value, dict):
        # LangAlt — emit ``rdf:Alt`` of ``rdf:li xml:lang="...">value</rdf:li>``.
        alt = doc.createElementNS(_RDF_NS, "rdf:Alt")
        elem.appendChild(alt)
        for lang, text in value.items():
            li = doc.createElementNS(_RDF_NS, "rdf:li")
            li.setAttribute("xml:lang", str(lang))
            li.appendChild(doc.createTextNode(_stringify(text)))
            alt.appendChild(li)
        return
    if isinstance(value, list):
        # Bag/Seq — emit ``rdf:Bag`` (or ``rdf:Seq`` for ordered date arrays).
        container = doc.createElementNS(_RDF_NS, "rdf:Bag")
        elem.appendChild(container)
        for item in value:
            li = doc.createElementNS(_RDF_NS, "rdf:li")
            li.appendChild(doc.createTextNode(_stringify(item)))
            container.appendChild(li)
        return
    elem.appendChild(doc.createTextNode(_stringify(value)))


def _stringify(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)

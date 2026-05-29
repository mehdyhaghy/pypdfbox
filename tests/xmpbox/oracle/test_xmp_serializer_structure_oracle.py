"""Live Apache xmpbox parity for the *structure* of pypdfbox-emitted packets.

Where ``test_xmp_round_trip_oracle.py`` checks that the property *values*
survive a pypdfbox-serialize → xmpbox-parse round trip, this file pins the
*shape* of the emitted XMP packet against Apache xmpbox 3.0.7's own
``XmpSerializer.serialize(metadata, os, withXpacket=true)`` output:

  * The packet starts with the ``<?xpacket?>`` PI and never with an
    ``<?xml ...?>`` prolog (upstream sets ``OMIT_XML_DECLARATION="yes"``).
  * The header PI carries the canonical id ``W5M0MpCehiHzreSzNTczkc9d`` and the
    trailer PI carries ``end="w"``.
  * The wrapper is ``x:xmpmeta`` containing ``rdf:RDF``.
  * One ``rdf:Description`` per schema, each with a (possibly empty)
    ``rdf:about`` and the schema prefix derived from its property elements.
  * Simple properties serialize as child *elements* (not attributes); array
    properties wrap their items in an ``rdf:Bag``/``Seq``/``Alt`` container of
    ``rdf:li`` children — Dublin Core ``title`` is an ``Alt``, ``creator`` a
    ``Seq``, ``subject`` a ``Bag``.

The comparison is whitespace- and namespace-placement-independent: both sides
reduce the packet to the same canonical structural dictionary. xmpbox
pretty-prints with two-space indentation and hoists the per-schema ``xmlns``
declarations onto ``rdf:RDF``; pypdfbox emits a compact packet and declares
each schema namespace on its ``rdf:Description``. Both are equivalent XML — the
structural dump ignores those legitimate divergences (documented in
CHANGES.md) and asserts on the load-bearing shape.
"""

from __future__ import annotations

import json
from io import BytesIO
from xml.dom.minidom import Element, parseString

from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import RDF_NAMESPACE, XMPMetadata
from tests.oracle.harness import requires_oracle, run_probe_text

_ARRAY_TYPES = {"Bag", "Seq", "Alt"}


def _build_metadata() -> XMPMetadata:
    """Mirror the fixed document the Java probe builds."""
    m = XMPMetadata.create_xmp_metadata()
    dc = m.add_dublin_core_schema()
    dc.set_title("Sample Title")
    dc.add_creator("Alice Smith")
    dc.add_subject("pdf")
    dc.add_subject("xmp")
    dc.set_format("application/pdf")
    ap = m.add_adobe_pdf_schema()
    ap.set_producer("pypdfbox/test")
    ap.set_keywords("k1, k2")
    ap.set_pdf_version("1.7")
    return m


def _child_elements(node) -> list[Element]:
    return [c for c in node.childNodes if c.nodeType == c.ELEMENT_NODE]


def _local_name(elem: Element) -> str:
    tag = elem.tagName
    return tag.split(":", 1)[1] if ":" in tag else tag


def _array_container(prop: Element) -> Element | None:
    for child in _child_elements(prop):
        if (
            child.namespaceURI == RDF_NAMESPACE
            and _local_name(child) in _ARRAY_TYPES
        ):
            return child
    return None


def _describe_property(prop: Element) -> dict:
    out: dict = {"name": _local_name(prop)}
    container = _array_container(prop)
    if container is not None:
        out["kind"] = "array"
        out["array_type"] = _local_name(container)
        out["li_count"] = len(_child_elements(container))
    else:
        out["kind"] = "simple"
        text = "".join(
            c.data for c in prop.childNodes if c.nodeType == c.TEXT_NODE
        )
        out["value"] = text
    return out


def _describe_description(desc: Element) -> dict:
    about = desc.getAttributeNS(RDF_NAMESPACE, "about")
    props = _child_elements(desc)
    prefix = ""
    if props:
        tag = props[0].tagName
        prefix = tag.split(":", 1)[0] if ":" in tag else ""
    return {
        "about": about,
        "prefix": prefix,
        "properties": [_describe_property(p) for p in props],
    }


def _pypdfbox_structure() -> dict:
    buf = BytesIO()
    XmpSerializer().serialize(_build_metadata(), buf)
    packet = buf.getvalue()
    text = packet.decode("utf-8")

    root: dict = {"starts_with_xml_decl": text.lstrip().startswith("<?xml")}

    doc = parseString(packet)
    for node in doc.childNodes:
        if node.nodeType == node.PROCESSING_INSTRUCTION_NODE and node.target == "xpacket":
            data = node.data
            if data.startswith("begin="):
                root["xpacket_begin_present"] = True
                root["xpacket_begin_id"] = _extract(data, "id")
            elif data.startswith("end="):
                root["xpacket_end"] = _extract(data, "end")

    xmpmeta = doc.documentElement
    root["root_tag"] = xmpmeta.tagName
    rdf = _child_elements(xmpmeta)[0]
    root["rdf_tag"] = rdf.tagName

    descriptions = [
        _describe_description(d)
        for d in rdf.getElementsByTagNameNS(RDF_NAMESPACE, "Description")
    ]
    root["descriptions"] = descriptions
    return root


def _extract(data: str, key: str) -> str | None:
    needle = f'{key}="'
    start = data.find(needle)
    if start < 0:
        return None
    start += len(needle)
    end = data.find('"', start)
    return None if end < 0 else data[start:end]


@requires_oracle
def test_serializer_structure_matches_xmpbox() -> None:
    java_dump = json.loads(run_probe_text("XmpSerializerStructureProbe"))
    py_dump = _pypdfbox_structure()
    assert py_dump == java_dump, (
        "serializer structure divergence:\n"
        f"  java: {json.dumps(java_dump, sort_keys=True, ensure_ascii=False)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True, ensure_ascii=False)}"
    )

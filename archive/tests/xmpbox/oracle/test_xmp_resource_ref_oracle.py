"""Live Apache xmpbox parity for ``rdf:parseType="Resource"`` structured types.

Closes the wave-1499 deferral: the ``xmpMM:DerivedFrom`` ``ResourceRefType``
round-trip had no oracle pin. Two surfaces are covered against Apache
xmpbox 3.0.7 via the ``XmpResourceRefProbe`` Java probe:

Parse direction
    A hand-crafted ``parseType="Resource"`` packet is parsed by BOTH the
    Java ``DomXmpParser`` (probe ``parse`` mode) and pypdfbox's
    :class:`DomXmpParser`, in strict and lenient modes. Both must surface the
    same typed ``ResourceRef`` structure — the same child field names/values
    and the same structure kind. (Upstream parses this identically in strict
    and lenient mode; pypdfbox must too.)

Serialize direction
    A ``ResourceRefType`` is constructed and installed on the media-management
    schema's ``DerivedFrom`` slot, then serialized. The probe's ``serialize``
    mode reports the upstream serializer's emitted DOM shape; pypdfbox must
    emit the same shape: a ``xmpMM:DerivedFrom`` wrapper (schema prefix, NOT
    the field's ``stRef`` prefix) enclosing a single
    ``<rdf:li rdf:parseType="Resource">`` whose children are the typed
    ``stRef:*`` fields.

The fixture is hand-crafted (raw XMP bytes) because upstream's public
construction API cannot emit a re-parseable ``parseType="Resource"`` packet:
``XmpSerializer`` writes the inner ``stRef:*`` fields without declaring the
``xmlns:stRef`` namespace, so the emitted packet is not re-parseable by
xmpbox's own parser. The serialize-direction parity therefore compares the
DOM *shape* (parsed namespace-unaware) rather than round-tripping the bytes.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from pypdfbox.xmpbox.type.resource_ref_type import ResourceRefType
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_media_management_schema import XMPMediaManagementSchema
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata
from tests.oracle.harness import requires_oracle, run_probe_text

_MM_NS = "http://ns.adobe.com/xap/1.0/mm/"
_STREF_NS = "http://ns.adobe.com/xap/1.0/sType/ResourceRef#"

# Hand-crafted parseType="Resource" packet (raw XMP bytes). The xmlns:stRef
# declaration is present here so a strict namespace-aware parser accepts it on
# the *parse* side — upstream's own serializer omits it, but a real-world
# producer (Adobe) always declares it.
_DERIVED_FROM_FIXTURE = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    '  <rdf:Description rdf:about=""\n'
    f'      xmlns:xmpMM="{_MM_NS}"\n'
    f'      xmlns:stRef="{_STREF_NS}">\n'
    '   <xmpMM:DerivedFrom rdf:parseType="Resource">\n'
    "    <stRef:instanceID>uuid:inst-123</stRef:instanceID>\n"
    "    <stRef:documentID>uuid:doc-456</stRef:documentID>\n"
    "    <stRef:renditionClass>default</stRef:renditionClass>\n"
    "    <stRef:versionID>7</stRef:versionID>\n"
    "   </xmpMM:DerivedFrom>\n"
    "  </rdf:Description>\n"
    " </rdf:RDF>\n"
    "</x:xmpmeta>\n"
    '<?xpacket end="w"?>'
).encode("utf-8")


def _pypdfbox_parse_dump(packet: bytes, *, lenient: bool) -> dict:
    """Parse ``packet`` with pypdfbox and emit the same JSON shape the probe's
    ``parse`` mode produces (``dumpFromMeta``)."""
    parser = DomXmpParser()
    if lenient:
        parser.set_strict_parsing(False)
    meta = parser.parse(packet)
    mm = meta.get_schema(XMPMediaManagementSchema)
    if mm is None:
        return {"derived_from_present": False}
    ref = mm.get_derived_from()
    if ref is None:
        return {"derived_from_present": False}
    fields: dict[str, str] = {}
    for field in ref.get_all_properties():
        name = field.get_property_name()
        value = field.get_string_value() if hasattr(field, "get_string_value") else None
        if name is not None and value is not None:
            fields[name] = value
    return {
        "derived_from_present": True,
        "kind": "structured",
        "fields": fields,
    }


@requires_oracle
@pytest.mark.parametrize("lenient", [False, True], ids=["strict", "lenient"])
def test_parse_resource_ref_matches_xmpbox(lenient: bool, tmp_path: Path) -> None:
    packet_path = tmp_path / "derived_from.xmp"
    packet_path.write_bytes(_DERIVED_FROM_FIXTURE)

    probe_args = ["parse", str(packet_path)]
    if lenient:
        probe_args.append("lenient")
    java_dump = json.loads(run_probe_text("XmpResourceRefProbe", *probe_args))
    py_dump = _pypdfbox_parse_dump(_DERIVED_FROM_FIXTURE, lenient=lenient)

    assert py_dump == java_dump, (
        "parseType=Resource divergence "
        f"({'lenient' if lenient else 'strict'}):\n"
        f"  java: {json.dumps(java_dump, sort_keys=True)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True)}"
    )


def _build_derived_from_metadata() -> XMPMetadata:
    meta = XMPMetadata.create_xmp_metadata()
    mm = meta.add_xmp_media_management_schema()
    ref = ResourceRefType(meta)
    ref.set_instance_id("uuid:inst-123")
    ref.set_document_id("uuid:doc-456")
    ref.set_rendition_class("default")
    ref.set_version_id("7")
    mm.set_derived_from(ref)
    return meta


def _pypdfbox_serialize_shape(packet: bytes) -> dict:
    """Parse ``packet`` namespace-unaware and emit the same DOM-shape JSON the
    probe's ``serialize`` mode produces (``domShape``)."""
    import xml.dom.minidom as minidom

    # Strip the xpacket PIs so minidom parses the bare RDF tree. Like the Java
    # probe, we only care about qualified tag names, not namespace binding —
    # but Python's expat (unlike a namespace-unaware DocumentBuilder) rejects
    # an unbound prefix. Upstream's serializer omits the xmlns:stRef
    # declaration, so inject a throwaway binding purely to make the fragment
    # well-formed for shape inspection.
    text = packet.decode("utf-8")
    start = text.index("<x:xmpmeta")
    end = text.index("</x:xmpmeta>") + len("</x:xmpmeta>")
    fragment = text[start:end]
    if "xmlns:stRef" not in fragment:
        fragment = fragment.replace(
            "<x:xmpmeta",
            f'<x:xmpmeta xmlns:stRef="{_STREF_NS}"',
            1,
        )
    doc = minidom.parseString(fragment)

    def find_by_tag(node, tag):
        if node.nodeType == node.ELEMENT_NODE and node.tagName == tag:
            return node
        for child in node.childNodes:
            if child.nodeType == child.ELEMENT_NODE:
                found = find_by_tag(child, tag)
                if found is not None:
                    return found
        return None

    derived = find_by_tag(doc.documentElement, "xmpMM:DerivedFrom")
    if derived is None:
        return {"dom": {"wrapper_found": False}}
    shape: dict = {"wrapper_found": True, "wrapper_tag": derived.tagName}
    li = None
    for child in derived.childNodes:
        if child.nodeType == child.ELEMENT_NODE and child.tagName == "rdf:li":
            li = child
            break
    if li is None:
        shape["has_rdf_li"] = False
        shape["wrapper_direct_parsetype"] = derived.getAttribute("rdf:parseType")
        return {"dom": shape}
    shape["has_rdf_li"] = True
    shape["li_parsetype"] = li.getAttribute("rdf:parseType")
    children = []
    for child in li.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            text_value = "".join(
                n.data for n in child.childNodes if n.nodeType == n.TEXT_NODE
            )
            children.append({"tag": child.tagName, "value": text_value})
    shape["li_children"] = children
    return {"dom": shape}


@requires_oracle
def test_serialize_resource_ref_shape_matches_xmpbox() -> None:
    java_dump = json.loads(run_probe_text("XmpResourceRefProbe", "serialize"))
    meta = _build_derived_from_metadata()
    buf = BytesIO()
    XmpSerializer().serialize(meta, buf)
    py_dump = _pypdfbox_serialize_shape(buf.getvalue())

    assert py_dump == java_dump, (
        "parseType=Resource serialize-shape divergence:\n"
        f"  java: {json.dumps(java_dump, sort_keys=True)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True)}"
    )

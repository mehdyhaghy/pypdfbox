"""Wave 1370 — :class:`XmpSerializer` envelope shape.

Covers the packet-envelope toggles that callers of XmpSerializer rely on:

* ``with_xpacket=True`` emits ``<?xpacket begin="..."?>`` and ``<?xpacket
  end="..."?>`` processing instructions around the meta element.
* ``with_xpacket=False`` suppresses both PIs (used by callers who embed
  the packet inside an existing wrapper).
* The :class:`XMPMetadata` xpacket attributes propagate verbatim into the
  emitted PI data (``begin`` value as the byte-order mark sentinel, the
  fixed ``id`` GUID).
* The ``x:xmpmeta`` wrapper always appears around ``rdf:RDF``.
* The ``rdf`` namespace is declared once on ``rdf:RDF``.
* ``save`` accepts an explicit encoding and uses it in the XML
  declaration.
"""

from __future__ import annotations

import io
from xml.dom.minidom import Document

from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


def _new_meta() -> XMPMetadata:
    meta = XMPMetadata.create_xmp_metadata()
    dc = meta.create_and_add_dublin_core_schema()
    dc.set_title_lang("x-default", "DocTitle")
    return meta


# ---------------------------------------------------------------------------
# xpacket PI emission toggle.
# ---------------------------------------------------------------------------


def test_serialize_with_xpacket_emits_begin_and_end_pis() -> None:
    out = io.BytesIO()
    XmpSerializer().serialize(_new_meta(), out, with_xpacket=True)
    blob = out.getvalue()
    assert b"<?xpacket begin=" in blob
    assert b"<?xpacket end=" in blob
    # GUID id used by Adobe-style packets.
    assert b"W5M0MpCehiHzreSzNTczkc9d" in blob


def test_serialize_without_xpacket_omits_pis() -> None:
    out = io.BytesIO()
    XmpSerializer().serialize(_new_meta(), out, with_xpacket=False)
    blob = out.getvalue()
    assert b"<?xpacket" not in blob


def test_serialize_with_xpacket_uses_metadata_begin_marker() -> None:
    meta = _new_meta()
    meta.set_xpacket_begin("﻿")  # BOM sentinel
    meta.set_xpacket_id("custom-packet-id")
    out = io.BytesIO()
    XmpSerializer().serialize(meta, out, with_xpacket=True)
    blob = out.getvalue()
    # The BOM byte sequence as UTF-8 must appear in the PI.
    assert b"\xef\xbb\xbf" in blob
    assert b"custom-packet-id" in blob


def test_serialize_with_xpacket_uses_metadata_end_marker() -> None:
    meta = _new_meta()
    meta.set_end_xpacket("r")  # read-only marker
    out = io.BytesIO()
    XmpSerializer().serialize(meta, out, with_xpacket=True)
    blob = out.getvalue()
    assert b'end="r"' in blob


# ---------------------------------------------------------------------------
# x:xmpmeta wrapper + xmlns declarations.
# ---------------------------------------------------------------------------


def test_serialize_always_wraps_rdf_in_x_xmpmeta() -> None:
    out = io.BytesIO()
    XmpSerializer().serialize(_new_meta(), out, with_xpacket=False)
    blob = out.getvalue()
    # Wrapper element + namespace declaration.
    assert b"x:xmpmeta" in blob
    assert b'xmlns:x="adobe:ns:meta/"' in blob


def test_serialize_declares_rdf_namespace_on_rdf_root() -> None:
    out = io.BytesIO()
    XmpSerializer().serialize(_new_meta(), out, with_xpacket=False)
    blob = out.getvalue()
    assert b"rdf:RDF" in blob
    assert (
        b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"' in blob
    )


def test_serialize_rdf_namespace_declared_only_once() -> None:
    out = io.BytesIO()
    XmpSerializer().serialize(_new_meta(), out, with_xpacket=False)
    blob = out.getvalue()
    # Only one xmlns:rdf declaration in the output.
    assert blob.count(b"xmlns:rdf=") == 1


# ---------------------------------------------------------------------------
# Schema namespace prefix declaration on rdf:Description.
# ---------------------------------------------------------------------------


def test_serialize_declares_schema_namespace_on_description() -> None:
    out = io.BytesIO()
    XmpSerializer().serialize(_new_meta(), out, with_xpacket=False)
    blob = out.getvalue()
    # Dublin Core's preferred prefix is dc.
    assert b'xmlns:dc="http://purl.org/dc/elements/1.1/"' in blob


def test_serialize_uses_rdf_about_attribute() -> None:
    meta = _new_meta()
    # Set a custom about value via the schema accessor.
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    dc.set_about("urn:test:doc:1")
    out = io.BytesIO()
    XmpSerializer().serialize(meta, out, with_xpacket=False)
    blob = out.getvalue()
    assert b'rdf:about="urn:test:doc:1"' in blob


# ---------------------------------------------------------------------------
# Encoding propagation via save().
# ---------------------------------------------------------------------------


def test_save_omits_xml_declaration() -> None:
    # Upstream XmpSerializer.save sets OMIT_XML_DECLARATION="yes"; the packet
    # must never start with an <?xml ...?> prolog (a prolog before the
    # <?xpacket?> PI is malformed XMP). save() of a bare element therefore
    # emits only the serialized node, with no declaration.
    doc = Document()
    root = doc.createElement("root")
    doc.appendChild(root)
    out = io.BytesIO()
    XmpSerializer().save(doc, out)
    blob = out.getvalue()
    assert not blob.startswith(b"<?xml")
    assert blob == b"<root/>"


def test_save_honours_explicit_encoding_kwarg() -> None:
    doc = Document()
    root = doc.createElement("root")
    text = doc.createTextNode("é")
    root.appendChild(text)
    doc.appendChild(root)
    out = io.BytesIO()
    XmpSerializer().save(doc, out, encoding="utf-16")
    blob = out.getvalue()
    # No XML declaration; the bytes decode back under the requested encoding.
    assert not blob.lstrip(b"\xff\xfe\xfe\xff").startswith(b"<?xml")
    assert blob.decode("utf-16") == "<root>é</root>"


def test_save_explicit_latin_1_encoding() -> None:
    doc = Document()
    root = doc.createElement("root")
    text = doc.createTextNode("é")
    root.appendChild(text)
    doc.appendChild(root)
    out = io.BytesIO()
    XmpSerializer().save(doc, out, encoding="iso-8859-1")
    blob = out.getvalue()
    # No declaration; the é byte is the latin-1 encoding of the text node.
    assert not blob.startswith(b"<?xml")
    assert blob.decode("iso-8859-1") == "<root>é</root>"


# ---------------------------------------------------------------------------
# normalize_attributes returns a list (used by parity scanners).
# ---------------------------------------------------------------------------


def test_normalize_attributes_for_property_without_attributes() -> None:
    class _Plain:
        pass

    ser = XmpSerializer()
    result = ser.normalize_attributes(_Plain())
    assert result == []


def test_normalize_attributes_collects_property_attributes() -> None:
    from pypdfbox.xmpbox.type.abstract_field import Attribute
    from pypdfbox.xmpbox.type.text_type import TextType

    meta = XMPMetadata.create_xmp_metadata()
    text = TextType(meta, "urn:x", "x", "v", "hello")
    text.set_attribute(Attribute("urn:q", "qual", "value"))
    ser = XmpSerializer()
    result = ser.normalize_attributes(text)
    assert len(result) == 1
    assert result[0].get_value() == "value"


def test_normalize_attributes_swallows_get_all_attributes_failure() -> None:
    """If ``get_all_attributes`` raises, return an empty list."""

    class _Bad:
        def get_all_attributes(self):
            raise RuntimeError("boom")

    ser = XmpSerializer()
    result = ser.normalize_attributes(_Bad())
    assert result == []


# ---------------------------------------------------------------------------
# create_rdf_element parity wrapper.
# ---------------------------------------------------------------------------


def test_create_rdf_element_parity_alias_returns_rdf_element() -> None:
    meta = _new_meta()
    doc = Document()
    ser = XmpSerializer()
    rdf = ser.create_rdf_element(doc, meta, with_xpacket=False)
    # The returned element is rdf:RDF.
    assert rdf.tagName == "rdf:RDF"
    # rdf:RDF lives inside x:xmpmeta.
    assert rdf.parentNode.tagName == "x:xmpmeta"


def test_create_rdf_element_with_xpacket_attaches_pis_to_document() -> None:
    meta = _new_meta()
    doc = Document()
    ser = XmpSerializer()
    ser.create_rdf_element(doc, meta, with_xpacket=True)
    # Two xpacket processing instructions should now sit on the document.
    pi_nodes = [
        node for node in doc.childNodes if node.nodeType == node.PROCESSING_INSTRUCTION_NODE
    ]
    assert len(pi_nodes) == 2
    assert pi_nodes[0].target == "xpacket"
    assert pi_nodes[1].target == "xpacket"

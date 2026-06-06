"""Hand-written parity coverage for ``rdf:parseType="Resource"`` structured
types in the XMP parser and serializer (wave 1502, agent D).

Closes the wave-1499 deferral: a single (``Cardinality.Simple``) structured
property such as ``xmpMM:DerivedFrom`` is serialized as
``<xmpMM:DerivedFrom><rdf:li rdf:parseType="Resource">…</rdf:li></…>`` and
parses back into a typed :class:`ResourceRefType`. These tests pin both
directions against pypdfbox's own parser/serializer (the oracle pin against
Apache xmpbox lives in ``tests/xmpbox/oracle/test_xmp_resource_ref_oracle``).
"""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from pypdfbox.xmpbox.type.resource_ref_type import ResourceRefType
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_media_management_schema import XMPMediaManagementSchema
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata

_MM_NS = "http://ns.adobe.com/xap/1.0/mm/"
_STREF_NS = "http://ns.adobe.com/xap/1.0/sType/ResourceRef#"


def _packet(prop_local: str = "DerivedFrom") -> bytes:
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about=""'
        f' xmlns:xmpMM="{_MM_NS}" xmlns:stRef="{_STREF_NS}">'
        f'<xmpMM:{prop_local} rdf:parseType="Resource">'
        "<stRef:instanceID>uuid:inst-123</stRef:instanceID>"
        "<stRef:documentID>uuid:doc-456</stRef:documentID>"
        "<stRef:renditionClass>default</stRef:renditionClass>"
        "<stRef:versionID>7</stRef:versionID>"
        f"</xmpMM:{prop_local}>"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")


@pytest.mark.parametrize("lenient", [False, True], ids=["strict", "lenient"])
def test_parse_derived_from_yields_typed_resource_ref(lenient: bool) -> None:
    parser = DomXmpParser()
    if lenient:
        parser.set_strict_parsing(False)
    meta = parser.parse(_packet())
    mm = meta.get_schema(XMPMediaManagementSchema)
    assert mm is not None
    ref = mm.get_derived_from()
    assert isinstance(ref, ResourceRefType)
    assert ref.get_instance_id() == "uuid:inst-123"
    assert ref.get_document_id() == "uuid:doc-456"
    assert ref.get_rendition_class() == "default"
    assert ref.get_version_id() == "7"
    # The typed instance carries the upstream property name on the slot.
    assert ref.get_property_name() == "DerivedFrom"


def test_parse_managed_from_yields_typed_resource_ref() -> None:
    parser = DomXmpParser()
    meta = parser.parse(_packet("ManagedFrom"))
    mm = meta.get_schema(XMPMediaManagementSchema)
    assert mm is not None
    ref = mm.get_managed_from()
    assert isinstance(ref, ResourceRefType)
    assert ref.get_instance_id() == "uuid:inst-123"


def test_parse_strict_and_lenient_agree() -> None:
    def dump(lenient: bool) -> dict[str, str | None]:
        parser = DomXmpParser()
        if lenient:
            parser.set_strict_parsing(False)
        ref = parser.parse(_packet()).get_schema(
            XMPMediaManagementSchema
        ).get_derived_from()
        return {
            "instance": ref.get_instance_id(),
            "document": ref.get_document_id(),
            "rendition": ref.get_rendition_class(),
            "version": ref.get_version_id(),
        }

    assert dump(False) == dump(True)


def test_empty_parse_type_resource_falls_back_to_text() -> None:
    # A parseType="Resource" wrapper with no child elements has nothing to
    # build a struct from; the parser must not crash and must not invent an
    # empty ResourceRef — it falls back to the plain text representation.
    packet = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        f'xmlns:xmpMM="{_MM_NS}">'
        '<xmpMM:DerivedFrom rdf:parseType="Resource"></xmpMM:DerivedFrom>'
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
    ).encode("utf-8")
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    meta = parser.parse(packet)
    mm = meta.get_schema(XMPMediaManagementSchema)
    assert mm is not None
    # No typed struct was built (empty container) — the slot holds plain text.
    assert mm.get_derived_from() is None


def _serialize(meta: XMPMetadata) -> str:
    buf = BytesIO()
    XmpSerializer().serialize(meta, buf)
    return buf.getvalue().decode("utf-8")


def test_serialize_derived_from_uses_schema_prefix_wrapper() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    mm = meta.add_xmp_media_management_schema()
    ref = ResourceRefType(meta)
    ref.set_instance_id("uuid:inst-123")
    ref.set_document_id("uuid:doc-456")
    mm.set_derived_from(ref)
    out = _serialize(meta)
    # Wrapper carries the SCHEMA prefix (xmpMM), not the field prefix (stRef).
    assert "<xmpMM:DerivedFrom>" in out
    assert "<stRef:DerivedFrom>" not in out
    # Inner rdf:li carries the parseType marker.
    assert '<rdf:li rdf:parseType="Resource">' in out
    # Typed fields keep their own stRef prefix inside the rdf:li.
    assert "<stRef:instanceID>uuid:inst-123</stRef:instanceID>" in out
    assert "<stRef:documentID>uuid:doc-456</stRef:documentID>" in out


def test_serialize_omits_inner_namespace_like_upstream() -> None:
    # Faithful-port behavior: upstream ``XmpSerializer`` emits the inner
    # ``stRef:*`` fields WITHOUT declaring ``xmlns:stRef`` (PDFBOX-2378 only
    # adds the namespace declaration for schema-level simple properties, not
    # for the typed children of a structured property). pypdfbox mirrors that,
    # so the serialized packet carries an undeclared ``stRef`` prefix and is
    # not re-parseable by the parser — identical to upstream's known limitation.
    meta = XMPMetadata.create_xmp_metadata()
    mm = meta.add_xmp_media_management_schema()
    ref = ResourceRefType(meta)
    ref.set_instance_id("uuid:inst-999")
    ref.set_rendition_class("thumbnail")
    mm.set_derived_from(ref)
    out = _serialize(meta)
    assert "<stRef:instanceID>" in out
    assert "xmlns:stRef" not in out

    # The undeclared prefix means a strict re-parse rejects the packet, exactly
    # as Apache xmpbox's own DomXmpParser does for its own serializer output.
    from pypdfbox.xmpbox.dom_xmp_parser import XmpParsingException

    with pytest.raises(XmpParsingException):
        DomXmpParser().parse(out.encode("utf-8"))

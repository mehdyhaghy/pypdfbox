"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/XMPMetaDataTest.java

The upstream ``testAddingSchem`` snippet is translated to the equivalent
``XMPSchema`` constructor + property-setter calls because the parser-facing
storage path remains primitive even though later waves add ``TypeMapping``
and typed property wrappers for explicit accessors. The two
``XmpSerializationException`` smoke tests exercise upstream's exception
type — pypdfbox raises a plain :class:`RuntimeError` from the (eventual)
serializer instead, so those tests are skipped here. ``testPDFBOX3257``
depends on the DOM XMP parser and lives in
``test_dom_xmp_parser.py`` already; it is not duplicated here.
"""

from __future__ import annotations

from pypdfbox.xmpbox import XMPMetadata, XMPSchema


def test_init_meta_data_with_info() -> None:
    # Mirror of upstream ``testInitMetaDataWithInfo``: the four-argument
    # ``createXMPMetadata`` factory must echo every xpacket header back
    # via the matching ``getXpacket*`` accessor.
    xpacket_begin, xpacket_id = "TESTBEG", "TESTID"
    xpacket_bytes, xpacket_encoding = "TESTBYTES", "TESTENCOD"
    metadata = XMPMetadata.create_xmp_metadata(
        xpacket_begin, xpacket_id, xpacket_bytes, xpacket_encoding
    )
    assert metadata.get_xpacket_begin() == xpacket_begin
    assert metadata.get_xpacket_id() == xpacket_id
    assert metadata.get_xpacket_bytes() == xpacket_bytes
    assert metadata.get_xpacket_encoding() == xpacket_encoding


def test_adding_schem() -> None:
    # Mirror of upstream ``testAddingSchem``: register two distinct
    # schemas and verify ``getSchema(nsURI)`` / ``getAllSchemas()``.
    # ``TypeMapping`` is omitted in cluster #1, so the upstream call to
    # ``metadata.getTypeMapping().createText(...)`` is dropped — the
    # registration semantics under test do not depend on it.
    metadata = XMPMetadata.create_xmp_metadata()
    tmp_ns_uri = "http://www.test.org/schem/"
    tmp = XMPSchema(metadata, namespace_uri=tmp_ns_uri, prefix="test")

    tmp2 = XMPSchema(
        metadata, namespace_uri="http://www.space.org/schem/", prefix="space"
    )

    metadata.add_schema(tmp)
    metadata.add_schema(tmp2)

    assert metadata.get_schema(tmp_ns_uri) is tmp
    assert metadata.get_schema("THIS URI NOT EXISTS !") is None

    vals = metadata.get_all_schemas()
    assert tmp in vals
    assert tmp2 in vals

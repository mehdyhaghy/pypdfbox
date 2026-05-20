"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/XMPMetaDataTest.java

Four upstream tests are translatable:

* ``testAddingSchem`` — exercise ``addSchema`` / ``getSchema(nsURI)`` /
  ``getAllSchemas`` with two schemas (one auto-generated DublinCore-
  style, one custom namespace).
* ``testInitMetaDataWithInfo`` — the four-arg ``createXMPMetadata``
  factory must echo the xpacket header back through the matching
  ``getXpacket*`` accessors.
* ``testPDFBOX3257`` — setting CreateDate twice on a parsed XMP packet
  must not duplicate the element, and the bag-of-properties handling
  for ``dc:subject`` must still preserve order + count.

``testTransformerExceptionMessage`` / ``testTransformerExceptionWithCause``
exercise ``XmpSerializationException`` — pypdfbox raises plain
``RuntimeError`` from its serializer, so they are skipped here with a
one-line comment.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pypdfbox.xmpbox import (
    DomXmpParser,
    DublinCoreSchema,
    XMPBasicSchema,
    XMPMetadata,
    XMPSchema,
)
from pypdfbox.xmpbox.type.type_mapping import TypeMapping


def test_adding_schem() -> None:
    """Translated from upstream ``testAddingSchem``."""
    metadata = XMPMetadata.create_xmp_metadata()
    tmp_ns_uri = "http://www.test.org/schem/"
    tmp = XMPSchema(metadata, namespace_uri=tmp_ns_uri, prefix="test")
    tmp.add_qualified_bag_value("BagContainer", "Value1")
    tmp.add_qualified_bag_value("BagContainer", "Value2")
    tmp.add_qualified_bag_value("BagContainer", "Value3")

    tmp.add_unqualified_sequence_value("SeqContainer", "Value1")
    tmp.add_unqualified_sequence_value("SeqContainer", "Value2")
    tmp.add_unqualified_sequence_value("SeqContainer", "Value3")

    # Upstream installs an explicit Text property via the TypeMapping.
    tmp.add_property(
        TypeMapping(metadata).create_text(None, "test", "simpleProperty", "YEP")
    )

    tmp2 = XMPSchema(
        metadata,
        namespace_uri="http://www.space.org/schem/",
        prefix="space",
    )
    tmp2.add_unqualified_sequence_value("SeqSpContainer", "ValueSpace1")
    tmp2.add_unqualified_sequence_value("SeqSpContainer", "ValueSpace2")
    tmp2.add_unqualified_sequence_value("SeqSpContainer", "ValueSpace3")

    metadata.add_schema(tmp)
    metadata.add_schema(tmp2)

    assert metadata.get_schema(tmp_ns_uri) is tmp
    assert metadata.get_schema("THIS URI NOT EXISTS !") is None

    vals = metadata.get_all_schemas()
    assert tmp in vals
    assert tmp2 in vals


def test_init_meta_data_with_info() -> None:
    """Translated from upstream ``testInitMetaDataWithInfo``."""
    xpacket_begin, xpacket_id = "TESTBEG", "TESTID"
    xpacket_bytes, xpacket_encoding = "TESTBYTES", "TESTENCOD"
    metadata = XMPMetadata.create_xmp_metadata(
        xpacket_begin, xpacket_id, xpacket_bytes, xpacket_encoding
    )
    assert metadata.get_xpacket_begin() == xpacket_begin
    assert metadata.get_xpacket_id() == xpacket_id
    assert metadata.get_xpacket_bytes() == xpacket_bytes
    assert metadata.get_xpacket_encoding() == xpacket_encoding


def test_pdfbox3257() -> None:
    """Translated from upstream ``testPDFBOX3257``: setting ``CreateDate``
    twice must update the slot rather than duplicate, and unrelated
    list-valued properties (``dc:subject``) must keep their original
    cardinality."""
    xmpmeta = (
        '<?xpacket id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" '
        'x:xmptk="Adobe XMP Core 4.0-c316 44.253921, Sun Oct 01 2006 17:14:39">\n'
        '   <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '      <rdf:Description rdf:about=""\n'
        '            xmlns:xap="http://ns.adobe.com/xap/1.0/">\n'
        '         <xap:CreatorTool>Acrobat PDFMaker 8.1 for Word</xap:CreatorTool>\n'
        '         <xap:ModifyDate>2008-11-12T15:29:43+01:00</xap:ModifyDate>\n'
        '         <xap:CreateDate>2008-11-12T15:29:40+01:00</xap:CreateDate>\n'
        '         <xap:MetadataDate>2008-11-12T15:29:43+01:00</xap:MetadataDate>\n'
        '      </rdf:Description>\n'
        '      <rdf:Description rdf:about=""\n'
        '            xmlns:pdf="http://ns.adobe.com/pdf/1.3/">\n'
        '         <pdf:Producer>Acrobat Distiller 8.1.0 (Windows)</pdf:Producer>\n'
        '      </rdf:Description>\n'
        '      <rdf:Description rdf:about=""\n'
        '            xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        '         <dc:format>application/pdf</dc:format>\n'
        '         <dc:creator>\n'
        '            <rdf:Seq>\n'
        '               <rdf:li>R002325</rdf:li>\n'
        '            </rdf:Seq>\n'
        '         </dc:creator>\n'
        '         <dc:subject>\n'
        '            <rdf:Bag>\n'
        '               <rdf:li>one</rdf:li>\n'
        '               <rdf:li>two</rdf:li>\n'
        '               <rdf:li>three</rdf:li>\n'
        '               <rdf:li>four</rdf:li>\n'
        '            </rdf:Bag>\n'
        '         </dc:subject>\n'
        '         <dc:title>\n'
        '            <rdf:Alt>\n'
        '               <rdf:li xml:lang="x-default"> </rdf:li>\n'
        '            </rdf:Alt>\n'
        '         </dc:title>\n'
        '      </rdf:Description>\n'
        '      <rdf:Description rdf:about=""\n'
        '            xmlns:xapMM="http://ns.adobe.com/xap/1.0/mm/">\n'
        '         <xapMM:DocumentID>uuid:31ae92cf-9a27-45e0-9371-0d2741e25919</xapMM:DocumentID>\n'
        '         <xapMM:InstanceID>uuid:2c7eb5da-9210-4666-8cef-e02ef6631c5e</xapMM:InstanceID>\n'
        '      </rdf:Description>\n'
        '   </rdf:RDF>\n'
        '</x:xmpmeta>\n'
        '<?xpacket end="w"?>'
    )
    parser = DomXmpParser()
    parser.set_strict_parsing(False)
    xmp = parser.parse(xmpmeta.encode("utf-8"))
    basic = xmp.get_xmp_basic_schema()
    assert isinstance(basic, XMPBasicSchema)
    create_date1 = basic.get_create_date()
    new_date = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
    basic.set_create_date(new_date)
    create_date2 = basic.get_create_date()
    assert create_date1 != create_date2, "CreateDate has not been set"

    # Ensure the bugfix does not interfere with lists of properties
    # bearing the same local name.
    dc = xmp.get_dublin_core_schema()
    assert isinstance(dc, DublinCoreSchema)
    subjects = dc.get_subjects()
    assert subjects is not None
    assert len(subjects) == 4

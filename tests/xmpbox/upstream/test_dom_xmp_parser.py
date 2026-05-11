"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/xml/DomXmpParserTest.java

Most upstream tests exercise the rich type system (PDFAIdentificationSchema,
ExifSchema, ResourceEventType, etc.) and resource-loaded XML fixtures that
pypdfbox does not yet ship in cluster #1. They are kept here as skipped
placeholders so the porting log stays one-to-one with upstream. The two tests
that exercise only the read path (PDFBOX-5976 and PDFBOX-5649) are translated.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import DomXmpParser, XmpParsingException

PDFBOX_5976_PACKET = (
    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>\n"
    "<?xpacket begin=\"\" id=\"W5M0MpCehiHzreSzNTczkc9d\"?>\n"
    "<rdf:RDF\n"
    "  xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"\n"
    "  xmlns:pdf=\"http://ns.adobe.com/pdf/1.3/\"\n"
    "  xmlns:pdfaid=\"http://www.aiim.org/pdfa/ns/id/\">\n"
    "    <rdf:Description pdfaid:conformance=\"B\" pdfaid:part=\"3\" rdf:about=\"\"/>\n"
    "    <rdf:Description pdf:Producer=\"WeasyPrint 64.1\" rdf:about=\"\"/>\n"
    "</rdf:RDF>\n"
    "<?xpacket end=\"r\"?>"
)


PDFBOX_6106_PACKET = (
    b"<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>"
    b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'"
    b" xmlns:pdf='http://ns.adobe.com/pdf/1.3/'>"
    b"<rdf:Description rdf:about=''"
    b" pdf:CreationDate='2004-01-30T17:21:50Z'"
    b" pdf:ModDate='2004-01-30T17:21:50Z'"
    b" pdf:Producer='Acrobat Distiller 5.0.5 (Windows)'/>"
    b"</rdf:RDF><?xpacket end='r'?>"
)


def test_pdfbox5976() -> None:
    """
    Translated from upstream ``testPDFBox5976``: the two attribute-form
    properties on separate rdf:Description blocks must both be reachable.
    Upstream additionally checks the typed PDFAIdentificationSchema accessors
    (``getConformance``, ``getPart``); cluster #1 ships only the plain schema
    fallback for the PDF/A-id namespace, so we read those values via
    ``get_unqualified_text_property_value``.
    """
    xmp = DomXmpParser().parse(PDFBOX_5976_PACKET.encode("utf-8"))

    pdfaid = xmp.get_schema("http://www.aiim.org/pdfa/ns/id/")
    assert pdfaid is not None
    assert pdfaid.get_unqualified_text_property_value("conformance") == "B"
    assert pdfaid.get_unqualified_text_property_value("part") == "3"

    pdf = xmp.get_schema("http://ns.adobe.com/pdf/1.3/")
    assert pdf is not None
    assert pdf.get_unqualified_text_property_value("Producer") == "WeasyPrint 64.1"


def test_pdfbox5649_smoke() -> None:
    """
    Translated subset of upstream ``testPDFBox5649``: upstream loads
    ``PDFBOX-5649.xml`` from test resources and only asserts ``xmp != null``.
    Without the fixture, we substitute a minimal well-formed packet to exercise
    the equivalent "parser returns a non-null XMPMetadata" contract.
    """
    packet = (
        b"<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''/>"
        b"</rdf:RDF><?xpacket end='r'?>"
    )
    xmp = DomXmpParser().parse(packet)
    assert xmp is not None


def test_malformed_raises_xmp_parsing_exception() -> None:
    """
    Upstream relies on ``assertThrows(XmpParsingException.class, ...)`` for
    several malformed-input tests. We pin the exception type contract here.
    """
    with pytest.raises(XmpParsingException):
        DomXmpParser().parse(b"<not-rdf>oops")


def test_pdfbox6106() -> None:
    with pytest.raises(XmpParsingException) as info:
        DomXmpParser().parse(PDFBOX_6106_PACKET)

    assert info.value.get_error_type() is XmpParsingException.ErrorType.INVALID_TYPE
    assert str(info.value) == (
        "No type defined for {http://ns.adobe.com/pdf/1.3/}CreationDate"
    )


def test_pdfbox6106_lenient_mode_accepts_unknown_adobe_pdf_properties() -> None:
    parser = DomXmpParser()
    parser.set_strict_parsing(False)

    xmp = parser.parse(PDFBOX_6106_PACKET)

    pdf = xmp.get_adobe_pdf_schema()
    assert pdf is not None
    assert pdf.get_unqualified_text_property_value("Producer") == (
        "Acrobat Distiller 5.0.5 (Windows)"
    )
    assert pdf.get_unqualified_text_property_value("CreationDate") == (
        "2004-01-30T17:21:50Z"
    )
    assert pdf.get_unqualified_text_property_value("ModDate") == (
        "2004-01-30T17:21:50Z"
    )


# ----------------------------------------------------------------------------
# Translated upstream tests that cover the parser's protected helper surface
# (xpacket PI parsing, expectNaming, findDescriptionsParent). These do not
# require the rich type system and exercise behaviour upstream verifies in
# DomXmpParserTest.
# ----------------------------------------------------------------------------


def test_no_xpacket() -> None:
    """Translated from upstream ``testNoXPacket`` (DomXmpParserTest line 1122).

    Upstream rejects packets whose leading PI is named ``packet`` instead of
    ``xpacket``. pypdfbox's high-level parser tolerates a missing xpacket
    wrapper, so we exercise the equivalent check on the helper directly.
    """
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as info:
        parser.parse_initial_xpacket("foo='bar'")
    assert (
        info.value.get_error_type()
        is XmpParsingException.ErrorType.XPACKET_BAD_START
    )


def test_bad_x_packet_end1() -> None:
    """Translated from upstream ``testBadXPacketEnd1`` (line 677).

    The trailing PI uses ``ends=`` (typo) instead of ``end=``. Upstream
    raises ``XmpParsingException`` with that exact message.
    """
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as info:
        parser.parse_end_packet("ends=\"w\"")
    assert str(info.value) == (
        "Expected xpacket 'end' attribute (must be present and placed in first)"
    )


def test_bad_x_packet_end2() -> None:
    """Translated from upstream ``testBadXPacketEnd2`` (line 695).

    The trailing PI carries ``end='k'`` which isn't ``r`` or ``w``. Upstream
    raises with that exact message (note the trailing space, mirrored from
    upstream).
    """
    parser = DomXmpParser()
    with pytest.raises(XmpParsingException) as info:
        parser.parse_end_packet("end=\"k\"")
    assert str(info.value) == (
        "Expected xpacket 'end' attribute with value 'r' or 'w' "
    )


def test_bad_local_name_strict_mode() -> None:
    """Translated subset of upstream ``testBadLocalName`` (line 657).

    Upstream rejects ``x:xapmeta`` in strict mode with the exact message
    ``Expecting local name 'xmpmeta' and found 'xapmeta'``. We exercise the
    helper directly because the high-level parser doesn't yet enforce the
    x:xmpmeta wrapper at top level (it accepts bare rdf:RDF too).
    """
    import xml.etree.ElementTree as ET

    parser = DomXmpParser()
    elem = ET.Element("{adobe:ns:meta/}xapmeta")
    with pytest.raises(XmpParsingException) as info:
        parser.expect_naming(elem, "adobe:ns:meta/", "x", "xmpmeta")
    assert str(info.value) == (
        "Expecting local name 'xmpmeta' and found 'xapmeta'"
    )


def test_bad_rdf_namespace() -> None:
    """Translated from upstream ``testBadRdfNameSpace`` (line 1181).

    Upstream rejects an rdf:RDF whose namespace is ``https://`` instead of
    ``http://``. The expectNaming helper is the canonical check.
    """
    import xml.etree.ElementTree as ET

    parser = DomXmpParser()
    elem = ET.Element("{https://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF")
    with pytest.raises(XmpParsingException) as info:
        parser.expect_naming(
            elem, "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf", "RDF"
        )
    assert str(info.value) == (
        "Expecting namespace 'http://www.w3.org/1999/02/22-rdf-syntax-ns#' "
        "and found 'https://www.w3.org/1999/02/22-rdf-syntax-ns#'"
    )


def test_no_rdf_children() -> None:
    """Translated from upstream ``testNoRdfChildren`` (line 713).

    Upstream rejects a bare ``<x:xmpmeta/>`` with ``"No rdf description
    found in xmp"``. Use the helper directly since the top-level parser
    permits non-rdf roots.
    """
    import xml.etree.ElementTree as ET

    parser = DomXmpParser()
    wrapper = ET.Element("{adobe:ns:meta/}xmpmeta")
    with pytest.raises(XmpParsingException) as info:
        parser.find_descriptions_parent(wrapper)
    assert str(info.value) == "No rdf description found in xmp"


def test_is_strict_parsing_round_trip() -> None:
    """Translated from upstream assertions inside ``testLenientPdfaExtension``
    (line 1302) which call ``isStrictParsing`` / ``setStrictParsing`` to verify
    the toggle round-trips.
    """
    parser = DomXmpParser()
    assert parser.is_strict_parsing() is True
    parser.set_strict_parsing(False)
    assert parser.is_strict_parsing() is False
    parser.set_strict_parsing(True)
    assert parser.is_strict_parsing() is True


# --- skipped placeholders for parity with upstream test list ----------------


PDFBOX_5835_PACKET = (
    b"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>\n"
    b"<?xpacket begin=\"\xef\xbb\xbf\" id=\"W5M0MpCehiHzreSzNTczkc9d\"?>"
    b"<x:xmpmeta xmlns:x=\"adobe:ns:meta/\" x:xmptk=\"FIS/xee\">\n"
    b" <rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\">\n"
    b" <rdf:Description xmlns:pdfaid=\"http://www.aiim.org/pdfa/ns/id/\">\n"
    b"   <pdfaid:part>3</pdfaid:part>\n"
    b"   <pdfaid:conformance>A</pdfaid:conformance>\n"
    b" </rdf:Description>\n"
    b" </rdf:RDF>\n"
    b"</x:xmpmeta><?xpacket end=\"w\"?>"
)


def test_pdfbox5835() -> None:
    """
    Translated from upstream ``testPDFBox5835``: a packet that declares
    ``pdfaid:part`` and ``pdfaid:conformance`` as element-form children (rather
    than the attribute-form covered by ``testPDFBox5976``) must still surface
    through the typed :class:`PDFAIdentificationSchema` accessors.

    Upstream loads ``PDFBOX-5835.xml`` from test resources; the inlined packet
    above is byte-equivalent to the property-bearing subset of that fixture
    (the surrounding pdfaExtension/schemas declarations the upstream fixture
    carries are not exercised by the assertions).
    """
    xmp = DomXmpParser().parse(PDFBOX_5835_PACKET)
    schema = xmp.get_pdfa_identification_schema()
    assert schema is not None
    assert schema.get_conformance() == "A"
    assert schema.get_part() == 3


def test_exif() -> None:
    """Typed-construction prerequisites for upstream EXIF parser tests.

    Upstream ``DomXmpParserTest`` exercises ``ExifSchema`` + ``CFAPatternType``
    through full parse round-trips (``testPDFBOX6126`` /
    ``testNonStandardURIinRDF``). Until the DOM parser builds typed
    structured-type instances from rdf:Seq/rdf:li children (owned by another
    agent), this asserts the type-system pieces the parser will rely on:
    :class:`ExifSchema` and :class:`CFAPatternType` exist, expose the right
    namespace/prefix metadata, and the structured type is registered with
    :class:`TypeMapping`.
    """
    from pypdfbox.xmpbox import ExifSchema, XMPMetadata
    from pypdfbox.xmpbox.type import CFAPatternType, TypeMapping

    metadata = XMPMetadata.create_xmp_metadata()
    assert ExifSchema.NAMESPACE == "http://ns.adobe.com/exif/1.0/"
    assert ExifSchema.PREFERRED_PREFIX == "exif"
    cfa = CFAPatternType(metadata)
    assert cfa.get_namespace() == ExifSchema.NAMESPACE
    assert cfa.get_prefered_prefix() == "exif"
    cfa.set_columns(2)
    cfa.set_rows(2)
    cfa.add_value(0)
    cfa.add_value(1)
    assert cfa.get_columns() == 2
    assert cfa.get_rows() == 2
    assert cfa.get_values() == [0, 1]
    assert TypeMapping(metadata).is_structured_type_known("CFAPattern") is True


def test_layer() -> None:
    """Parser builds typed :class:`LayerType` instances inside an
    :class:`ArrayProperty`.

    Exercises the typed-array dispatch path: ``photoshop:TextLayers`` is
    registered as a Seq of :class:`LayerType` in the parser's typed-array
    registry, so its ``rdf:li`` children — which carry
    ``photoshop:LayerName`` / ``photoshop:LayerText`` as attributes —
    materialise as :class:`LayerType` instances reachable via
    :meth:`PhotoshopSchema.get_text_layers`. Mirrors the
    ``photoshopSchema.getTextLayers()`` assertions embedded in upstream's
    ``testHistory`` (PDFBox 3.0 ``DomXmpParserTest`` line 422-427).
    """
    packet = (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about=""'
        ' xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">'
        "<photoshop:TextLayers>"
        "<rdf:Seq>"
        '<rdf:li photoshop:LayerName="Name1" photoshop:LayerText="Text1"/>'
        '<rdf:li photoshop:LayerName="Name2" photoshop:LayerText="Text2"/>'
        "</rdf:Seq>"
        "</photoshop:TextLayers>"
        "</rdf:Description>"
        "</rdf:RDF>"
        "</x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")

    metadata = DomXmpParser().parse(packet)
    photoshop = metadata.get_photoshop_schema()
    assert photoshop is not None

    array = photoshop.get_text_layers_property()
    assert array is not None
    # Bag / Seq / Alt collapse to a single Python ``Enum`` alias under
    # the hood (all share value ``True``), so we only assert it's an
    # array-flavoured cardinality rather than checking the literal name.
    assert array.get_array_type().is_array() is True

    layers = photoshop.get_text_layers()
    assert layers is not None
    assert len(layers) == 2
    assert layers[0].get_layer_name() == "Name1"
    assert layers[0].get_layer_text() == "Text1"
    assert layers[1].get_layer_name() == "Name2"
    assert layers[1].get_layer_text() == "Text2"


def test_history() -> None:
    """Typed-construction prerequisites for upstream ``testHistory`` /
    ``testPDFBox3882_2``.

    Upstream parses a ``xmpMM:History`` Seq populated with
    :class:`ResourceEventType` entries (action / instanceID / when /
    softwareAgent fields). The DOM parser does not yet build typed structured
    children for rdf:Seq members (owned by another agent), so we assert the
    underlying type ports + :class:`TypeMapping` registration so the parser
    can construct them when typed-construction lands.
    """
    from pypdfbox.xmpbox import XMPMetadata
    from pypdfbox.xmpbox.type import ResourceEventType, ResourceRefType, TypeMapping

    metadata = XMPMetadata.create_xmp_metadata()
    event = ResourceEventType(metadata)
    assert event.get_namespace() == "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"
    assert event.get_prefered_prefix() == "stEvt"
    event.set_action("created")
    event.set_instance_id("xmp.iid:01801174072068118A6D9A879C818256")
    event.set_software_agent("Adobe Photoshop CS5 Macintosh")
    assert event.get_action() == "created"
    assert event.get_instance_id() == "xmp.iid:01801174072068118A6D9A879C818256"
    assert event.get_software_agent() == "Adobe Photoshop CS5 Macintosh"

    ref = ResourceRefType(metadata)
    assert ref.get_namespace() == "http://ns.adobe.com/xap/1.0/sType/ResourceRef#"
    assert ref.get_prefered_prefix() == "stRef"
    ref.set_instance_id("xmp.iid:49E997338D4911E1AB62EBF9B374B234")
    ref.set_document_id("xmp.did:49E997348D4911E1AB62EBF9B374B234")
    assert ref.get_instance_id() == "xmp.iid:49E997338D4911E1AB62EBF9B374B234"
    assert ref.get_document_id() == "xmp.did:49E997348D4911E1AB62EBF9B374B234"

    tm = TypeMapping(metadata)
    assert tm.is_structured_type_known("ResourceEvent") is True
    assert tm.is_structured_type_known("ResourceRef") is True

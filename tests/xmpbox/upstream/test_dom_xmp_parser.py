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


@pytest.mark.skip(reason="needs PDFBOX-5835.xml fixture + PDFAIdentificationSchema typed accessors")
def test_pdfbox5835() -> None:
    pass


@pytest.mark.skip(reason="needs ExifSchema + CFAPatternType (rich type system, not yet ported)")
def test_exif() -> None:
    pass


@pytest.mark.skip(
    reason="LayerType + PhotoshopSchema typed accessors are ported, but the "
    "DOM parser does not yet build typed structured-type instances from "
    "rdf:Seq/rdf:li children — TextLayers parses as a plain list rather than "
    "an ArrayProperty of LayerType. Un-skip when parser typed-construction lands."
)
def test_layer() -> None:
    pass


@pytest.mark.skip(
    reason="needs ResourceEventType / ResourceRefType (rich type system, not yet ported)"
)
def test_history() -> None:
    pass

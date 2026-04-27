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


# --- skipped placeholders for parity with upstream test list ----------------


@pytest.mark.skip(reason="needs PDFBOX-5835.xml fixture + PDFAIdentificationSchema typed accessors")
def test_pdfbox5835() -> None:
    pass


@pytest.mark.skip(reason="needs strict-mode parser flag (deferred from cluster #1)")
def test_pdfbox6106() -> None:
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


@pytest.mark.skip(reason="needs ResourceEventType / ResourceRefType (rich type system, not yet ported)")
def test_history() -> None:
    pass

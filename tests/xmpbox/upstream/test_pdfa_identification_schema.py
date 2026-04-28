"""Ported from upstream PDFBox 3.0 tests:

* ``xmpbox/src/test/java/org/apache/xmpbox/schema/PDFAIdentificationOthersTest.java``
* ``xmpbox/src/test/java/org/apache/xmpbox/schema/PDFAIdentificationTest.java``

The pytest translations follow PRD §12.1's mapping table. Behaviour
sensitive to upstream's typed ``IntegerType`` / ``TextType`` field
hierarchy (``getPartProperty().getStringValue()`` round-trips) is
exercised through pypdfbox's flatter property store, since the typed
field hierarchy is not yet ported in cluster #1 of xmpbox.
"""
from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    BadFieldValueException,
    DomXmpParser,
    PDFAIdentificationSchema,
    XMPMetadata,
)


# ---------- PDFAIdentificationOthersTest ----------


def test_pdfa_identification() -> None:
    """Upstream ``testPDFAIdentification``: round-trip part / amd /
    conformance through the XMP packet and verify the parsed schema
    matches the original values."""
    metadata = XMPMetadata.create_xmp_metadata()
    pdfaid = metadata.add_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)

    version_id = 1
    amd_id = "2005"
    conformance = "B"

    pdfaid.set_part_value_with_int(version_id)
    pdfaid.set_amd(amd_id)
    pdfaid.set_conformance(conformance)

    assert pdfaid.get_part() == version_id
    assert pdfaid.get_amendment() == amd_id
    assert pdfaid.get_conformance() == conformance

    # Round-trip through a hand-rolled XMP packet — pypdfbox does not yet
    # ship an upstream-shaped XmpSerializer. The parser path is the same
    # one upstream's reparse exercises.
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:pdfaid='http://www.aiim.org/pdfa/ns/id/'"
        b" pdfaid:part='" + str(version_id).encode("utf-8") + b"'"
        b" pdfaid:amd='" + amd_id.encode("utf-8") + b"'"
        b" pdfaid:conformance='" + conformance.encode("utf-8") + b"'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    rxmp = DomXmpParser().parse(packet)
    pdfaid2 = rxmp.get_pdfa_identification_schema()
    assert isinstance(pdfaid2, PDFAIdentificationSchema)

    assert pdfaid2.get_part() == version_id
    assert pdfaid2.get_amendment() == amd_id
    assert pdfaid2.get_conformance() == conformance


def test_bad_pdfa_conformance_id() -> None:
    """Upstream ``testBadPDFAConformanceId``: invalid conformance
    raises ``BadFieldValueException``."""
    metadata = XMPMetadata.create_xmp_metadata()
    pdfaid = metadata.add_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)
    with pytest.raises(BadFieldValueException):
        pdfaid.set_conformance("kiohiohiohiohio")


def test_bad_version_id_value_type() -> None:
    """Upstream ``testBadVersionIdValueType``: a numeric string is
    accepted, garbage raises ``ValueError`` (mirrors upstream's
    ``IllegalArgumentException``)."""
    metadata = XMPMetadata.create_xmp_metadata()
    pdfaid = metadata.add_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)
    pdfaid.set_part_value_with_string("1")
    with pytest.raises(ValueError):
        pdfaid.set_part_value_with_string("ojoj")


# ---------- PDFAIdentificationTest (parameterised) ----------
#
# Upstream uses XMPSchemaTester#testGetSetValue and #testGetSetProperty
# over four (property, type, value) tuples. Without the typed-field
# hierarchy we exercise the value channel directly: set via the typed
# accessor, read back via ``get_*``.


@pytest.mark.parametrize(
    ("property_name", "value"),
    [
        ("part", 1),
        ("amd", "2005"),
        ("conformance", "B"),
        ("rev", 2020),
    ],
)
def test_element_value(property_name: str, value: object) -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    pdfaid = metadata.add_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)
    if property_name == "part":
        pdfaid.set_part(int(value))  # type: ignore[arg-type]
        assert pdfaid.get_part() == value
    elif property_name == "amd":
        pdfaid.set_amd(str(value))
        assert pdfaid.get_amd() == value
    elif property_name == "conformance":
        pdfaid.set_conformance(str(value))
        assert pdfaid.get_conformance() == value
    elif property_name == "rev":
        pdfaid.set_rev(int(value))  # type: ignore[arg-type]
        assert pdfaid.get_rev() == value
    else:  # pragma: no cover — parametrize guards this
        pytest.fail(f"unhandled property {property_name!r}")

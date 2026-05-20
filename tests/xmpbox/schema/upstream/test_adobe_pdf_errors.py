"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/AdobePDFErrorsTest.java

Three tests:

* ``testPDFAIdentification`` — round-trips Keywords / PDFVersion /
  Producer through a (serialize → parse) cycle and asserts the typed
  ``getXxxProperty()`` accessors recover the original property names.
* ``testBadPDFAConformanceId`` — passing an invalid conformance level
  to ``setConformance`` must raise ``BadFieldValueException``.
* ``testBadVersionIdValueType`` — ``setPartValueWithString("ojoj")``
  must raise the equivalent of upstream ``IllegalArgumentException``.

The Python translation maps ``IllegalArgumentException`` to
:class:`ValueError` (pypdfbox raises ``ValueError`` for non-numeric
strings to mirror the upstream contract).
"""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.xmpbox import (
    AdobePDFSchema,
    BadFieldValueException,
    DomXmpParser,
    PDFAIdentificationSchema,
    XMPMetadata,
)
from pypdfbox.xmpbox.xml import XmpSerializer


@pytest.fixture
def metadata() -> XMPMetadata:
    """Mirror of upstream's instance-field ``metadata``."""
    return XMPMetadata.create_xmp_metadata()


def test_pdfa_identification(metadata: XMPMetadata) -> None:
    """Translated from upstream ``testPDFAIdentification``: round-trip
    Keywords / PDFVersion / Producer through the XMP serializer +
    parser and check that the typed property accessors recover the
    upstream-named ``Keywords`` / ``PDFVersion`` / ``Producer`` local
    names along with their string values."""
    schema = metadata.create_and_add_adobe_pdf_schema()

    keywords = "keywords ihih"
    pdf_version = "1.4"
    producer = "producer"

    schema.set_keywords(keywords)
    schema.set_pdf_version(pdf_version)

    # Mirror upstream's null-check before producer is set.
    assert schema.get_producer() is None

    schema.set_producer(producer)

    assert schema.get_keywords_property().get_property_name() == "Keywords"
    assert schema.get_keywords() == keywords

    assert schema.get_pdf_version_property().get_property_name() == "PDFVersion"
    assert schema.get_pdf_version() == pdf_version

    assert schema.get_producer_property().get_property_name() == "Producer"
    assert schema.get_producer() == producer

    # Upstream ``assertEquals(schem, metadata.getAdobePDFSchema())`` —
    # in pypdfbox identity check is sufficient (no value-equality
    # override on the schema base class).
    assert metadata.get_adobe_pdf_schema() is schema

    # Round-trip through the serializer + parser.
    bos = BytesIO()
    XmpSerializer().serialize(metadata, bos, True)
    reparsed = DomXmpParser().parse(bos.getvalue())
    schema = reparsed.get_adobe_pdf_schema()
    assert isinstance(schema, AdobePDFSchema)

    assert schema.get_keywords_property().get_property_name() == "Keywords"
    assert schema.get_keywords() == keywords

    assert schema.get_pdf_version_property().get_property_name() == "PDFVersion"
    assert schema.get_pdf_version() == pdf_version

    assert schema.get_producer_property().get_property_name() == "Producer"
    assert schema.get_producer() == producer


def test_bad_pdfa_conformance_id(metadata: XMPMetadata) -> None:
    """Translated from upstream ``testBadPDFAConformanceId``: passing a
    value outside ``{A, B, U, e, f}`` raises ``BadFieldValueException``."""
    pdfaid = metadata.create_and_add_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)
    with pytest.raises(BadFieldValueException):
        pdfaid.set_conformance("kiohiohiohiohio")


def test_bad_version_id_value_type(metadata: XMPMetadata) -> None:
    """Translated from upstream ``testBadVersionIdValueType``: the
    numeric string ``"1"`` is accepted, but ``"ojoj"`` raises the
    pypdfbox equivalent of ``IllegalArgumentException`` (``ValueError``)."""
    pdfaid = metadata.create_and_add_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)
    pdfaid.set_part_value_with_string("1")
    with pytest.raises(ValueError):
        pdfaid.set_part_value_with_string("ojoj")

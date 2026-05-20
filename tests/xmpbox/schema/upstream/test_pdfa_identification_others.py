"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/PDFAIdentificationOthersTest.java

Three tests:

* ``testPDFAIdentification`` — round-trip ``part`` / ``amd`` /
  ``conformance`` through the XMP serializer + parser. Property names
  + values survive both sides.
* ``testBadPDFAConformanceId`` — invalid conformance level raises
  ``BadFieldValueException``.
* ``testBadVersionIdValueType`` — non-numeric ``setPartValueWithString``
  raises ``ValueError`` (pypdfbox's equivalent of upstream's
  ``IllegalArgumentException``).
"""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.xmpbox import (
    BadFieldValueException,
    DomXmpParser,
    PDFAIdentificationSchema,
    XMPMetadata,
)
from pypdfbox.xmpbox.xml import XmpSerializer


def test_pdfa_identification() -> None:
    """Translated from upstream ``testPDFAIdentification``."""
    metadata = XMPMetadata.create_xmp_metadata()
    pdfaid = metadata.create_and_add_pdfa_identification_schema()
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

    assert pdfaid.get_part_property().get_string_value() == str(version_id)
    assert pdfaid.get_amd_property().get_string_value() == amd_id
    assert pdfaid.get_conformance_property().get_string_value() == conformance

    # Mirror upstream's identity-via-equality check.
    assert metadata.get_pdfa_identification_schema() is pdfaid

    # Round-trip through serializer + parser.
    bos = BytesIO()
    XmpSerializer().serialize(metadata, bos, True)
    rxmp = DomXmpParser().parse(bos.getvalue())
    pdfaid = rxmp.get_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)

    assert pdfaid.get_part() == version_id
    assert pdfaid.get_amendment() == amd_id
    assert pdfaid.get_conformance() == conformance

    assert pdfaid.get_part_property().get_string_value() == str(version_id)
    assert pdfaid.get_amd_property().get_string_value() == amd_id
    assert pdfaid.get_conformance_property().get_string_value() == conformance


def test_bad_pdfa_conformance_id() -> None:
    """Translated from upstream ``testBadPDFAConformanceId``."""
    metadata = XMPMetadata.create_xmp_metadata()
    pdfaid = metadata.create_and_add_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)
    with pytest.raises(BadFieldValueException):
        pdfaid.set_conformance("kiohiohiohiohio")


def test_bad_version_id_value_type() -> None:
    """Translated from upstream ``testBadVersionIdValueType``."""
    metadata = XMPMetadata.create_xmp_metadata()
    pdfaid = metadata.create_and_add_pdfa_identification_schema()
    assert isinstance(pdfaid, PDFAIdentificationSchema)
    pdfaid.set_part_value_with_string("1")
    with pytest.raises(ValueError):
        pdfaid.set_part_value_with_string("ojoj")

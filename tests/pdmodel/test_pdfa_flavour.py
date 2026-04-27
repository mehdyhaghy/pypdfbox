"""Tests for the passive PDF/A flavour detector.

This is a pypdfbox addition with no upstream PDFBox equivalent — PDFBox 3.0
ships no flavour-detection helper. The detector reports what the metadata
*claims*; it does not validate.
"""
from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDMetadata
from pypdfbox.pdmodel.pdfa_flavour import KNOWN_FLAVOURS, PDFAFlavour
from pypdfbox.xmpbox import PDFAIdentificationSchema, XMPMetadata


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _xmp_packet(part: int, conformance: str | None) -> bytes:
    """Build a minimal XMP packet that declares a pdfaid identification block.

    Hand-rolled rather than going through a serializer because pypdfbox does
    not yet ship an XMP serializer (only the DOM parser). The byte shape here
    mirrors what real-world PDF/A producers emit.
    """
    pdfaid_attrs = f'pdfaid:part="{part}"'
    if conformance is not None:
        pdfaid_attrs += f' pdfaid:conformance="{conformance}"'
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/" '
        f"{pdfaid_attrs}/>"
        "</rdf:RDF>"
        "</x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# PDFAFlavour value object
# ---------------------------------------------------------------------------


def test_flavour_normalises_conformance_to_upper_case() -> None:
    f = PDFAFlavour(2, "b")
    assert f.conformance == "B"
    assert f == PDFAFlavour(2, "B")


def test_flavour_str_renders_human_readable() -> None:
    assert str(PDFAFlavour(1, "A")) == "PDF/A-1A"
    assert str(PDFAFlavour(2, "B")) == "PDF/A-2B"
    assert str(PDFAFlavour(3, "U")) == "PDF/A-3U"
    assert str(PDFAFlavour(4, "")) == "PDF/A-4"
    assert str(PDFAFlavour(4, "E")) == "PDF/A-4E"


def test_flavour_is_hashable_and_frozen() -> None:
    f = PDFAFlavour(2, "B")
    # frozen dataclass: assignment fails.
    with pytest.raises(Exception):
        f.part = 3  # type: ignore[misc]
    # hashable: usable as a dict / set key.
    assert {f: "ok"}[PDFAFlavour(2, "B")] == "ok"


# ---------------------------------------------------------------------------
# KNOWN_FLAVOURS table
# ---------------------------------------------------------------------------


def test_known_flavours_covers_all_canonical_combinations() -> None:
    expected = {
        PDFAFlavour(1, "A"),
        PDFAFlavour(1, "B"),
        PDFAFlavour(2, "A"),
        PDFAFlavour(2, "B"),
        PDFAFlavour(2, "U"),
        PDFAFlavour(3, "A"),
        PDFAFlavour(3, "B"),
        PDFAFlavour(3, "U"),
        PDFAFlavour(4, ""),
        PDFAFlavour(4, "E"),
        PDFAFlavour(4, "F"),
    }
    assert KNOWN_FLAVOURS == expected


def test_is_known_for_canonical_and_invalid_flavours() -> None:
    assert PDFAFlavour(2, "B").is_known() is True
    assert PDFAFlavour(4, "").is_known() is True
    assert PDFAFlavour(4, "E").is_known() is True
    # 1U does not exist (parts 2 & 3 only support U).
    assert PDFAFlavour(1, "U").is_known() is False
    # Made-up part number.
    assert PDFAFlavour(7, "B").is_known() is False


# ---------------------------------------------------------------------------
# from_xmp
# ---------------------------------------------------------------------------


def test_from_xmp_returns_none_for_none_input() -> None:
    assert PDFAFlavour.from_xmp(None) is None


def test_from_xmp_returns_none_when_no_pdfaid_schema() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    # No PDF/A identification schema attached.
    assert PDFAFlavour.from_xmp(meta) is None


def test_from_xmp_reads_part_and_conformance() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.add_pdfa_identification_schema()
    assert isinstance(schema, PDFAIdentificationSchema)
    schema.set_part(2)
    schema.set_conformance("B")

    flavour = PDFAFlavour.from_xmp(meta)
    assert flavour == PDFAFlavour(2, "B")
    assert flavour is not None
    assert flavour.is_known() is True


def test_from_xmp_part_4_omits_conformance() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.add_pdfa_identification_schema()
    assert isinstance(schema, PDFAIdentificationSchema)
    schema.set_part(4)
    # Per ISO 19005-4 plain part-4 has no pdfaid:conformance.
    flavour = PDFAFlavour.from_xmp(meta)
    assert flavour == PDFAFlavour(4, "")
    assert flavour is not None
    assert flavour.is_known() is True


def test_from_xmp_returns_none_when_part_missing() -> None:
    # A pdfaid schema with conformance but no part is malformed; treat as
    # "no detectable flavour".
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.add_pdfa_identification_schema()
    assert isinstance(schema, PDFAIdentificationSchema)
    schema.set_conformance("B")
    assert PDFAFlavour.from_xmp(meta) is None


# ---------------------------------------------------------------------------
# from_document
# ---------------------------------------------------------------------------


def test_from_document_returns_none_when_no_metadata_stream() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        assert PDFAFlavour.from_document(doc) is None
    finally:
        doc.close()


def test_from_document_reads_pdfa_2b_from_xmp_packet() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.set_metadata(PDMetadata(_xmp_packet(2, "B")))

        flavour = PDFAFlavour.from_document(doc)
        assert flavour == PDFAFlavour(2, "B")
    finally:
        doc.close()


def test_from_document_reads_pdfa_4_without_conformance() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.set_metadata(PDMetadata(_xmp_packet(4, None)))

        flavour = PDFAFlavour.from_document(doc)
        assert flavour == PDFAFlavour(4, "")
    finally:
        doc.close()


def test_from_document_returns_none_when_xmp_lacks_pdfaid() -> None:
    plain_xmp = (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'dc:format="application/pdf"/>'
        "</rdf:RDF>"
        "</x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.set_metadata(PDMetadata(plain_xmp))

        assert PDFAFlavour.from_document(doc) is None
    finally:
        doc.close()


def test_from_document_returns_none_for_malformed_xmp() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.set_metadata(PDMetadata(b"this is not XML at all"))

        # Malformed packet → no flavour, not a crash. A passive detector
        # should never raise on bad metadata.
        assert PDFAFlavour.from_document(doc) is None
    finally:
        doc.close()

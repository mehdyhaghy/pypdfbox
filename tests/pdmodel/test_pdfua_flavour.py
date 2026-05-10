"""Tests for the passive PDF/UA flavour detector.

This is a pypdfbox addition with no upstream PDFBox equivalent — PDFBox 3.0
ships no PDF/UA flavour-detection helper. The detector reports what the
metadata *claims*; it does not validate.
"""
from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDMetadata
from pypdfbox.pdmodel.pdfua_flavour import KNOWN_PARTS, PDFUAFlavour
from pypdfbox.xmpbox import PDFUAIdentificationSchema, XMPMetadata

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _xmp_packet(part: int, rev: str | None = None, conformance: str | None = None) -> bytes:
    """Build a minimal XMP packet that declares a pdfuaid identification block.

    Hand-rolled rather than going through a serializer because pypdfbox does
    not yet ship an XMP serializer (only the DOM parser). The byte shape here
    mirrors what real-world PDF/UA producers emit.
    """
    pdfua_attrs = f'pdfuaid:part="{part}"'
    if conformance is not None:
        pdfua_attrs += f' pdfuaid:conformance="{conformance}"'
    if rev is not None:
        pdfua_attrs += f' pdfuaid:rev="{rev}"'
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/" '
        f"{pdfua_attrs}/>"
        "</rdf:RDF>"
        "</x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# PDFUAFlavour value object
# ---------------------------------------------------------------------------


def test_flavour_str_renders_human_readable() -> None:
    assert str(PDFUAFlavour(1)) == "PDF/UA-1"
    assert str(PDFUAFlavour(2)) == "PDF/UA-2"
    assert str(PDFUAFlavour(1, "2014")) == "PDF/UA-1 (2014)"


def test_flavour_default_rev_is_none() -> None:
    f = PDFUAFlavour(1)
    assert f.rev is None


def test_flavour_is_hashable_and_frozen() -> None:
    f = PDFUAFlavour(1, "2014")
    # frozen dataclass: assignment fails.
    with pytest.raises(Exception):
        f.part = 2  # type: ignore[misc]
    # hashable: usable as a dict / set key.
    assert {f: "ok"}[PDFUAFlavour(1, "2014")] == "ok"


def test_flavour_equality() -> None:
    assert PDFUAFlavour(1) == PDFUAFlavour(1)
    assert PDFUAFlavour(1, "2014") == PDFUAFlavour(1, "2014")
    assert PDFUAFlavour(1, "2014") != PDFUAFlavour(1, "2024")
    assert PDFUAFlavour(1) != PDFUAFlavour(2)


# ---------------------------------------------------------------------------
# KNOWN_PARTS table
# ---------------------------------------------------------------------------


def test_known_parts_covers_published_iso_parts() -> None:
    # ISO 14289-1 (2014) and ISO 14289-2 (2024) — both published.
    assert frozenset({1, 2}) == KNOWN_PARTS


def test_is_known_for_canonical_and_invalid_parts() -> None:
    assert PDFUAFlavour(1).is_known() is True
    assert PDFUAFlavour(2).is_known() is True
    # Made-up part number — flavour should still build, just not be "known".
    assert PDFUAFlavour(7).is_known() is False
    assert PDFUAFlavour(99, "2099").is_known() is False


# ---------------------------------------------------------------------------
# from_xmp
# ---------------------------------------------------------------------------


def test_from_xmp_returns_none_for_none_input() -> None:
    assert PDFUAFlavour.from_xmp(None) is None


def test_from_xmp_returns_none_when_no_pdfuaid_schema() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    # No PDF/UA identification schema attached.
    assert PDFUAFlavour.from_xmp(meta) is None


def test_from_xmp_reads_part_only() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.add_pdfua_identification_schema()
    assert isinstance(schema, PDFUAIdentificationSchema)
    schema.set_part(1)

    flavour = PDFUAFlavour.from_xmp(meta)
    assert flavour == PDFUAFlavour(1)
    assert flavour is not None
    assert flavour.is_known() is True
    assert flavour.rev is None


def test_from_xmp_reads_part_and_rev() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.add_pdfua_identification_schema()
    assert isinstance(schema, PDFUAIdentificationSchema)
    schema.set_part(1)
    schema.set_revision("2014")

    flavour = PDFUAFlavour.from_xmp(meta)
    assert flavour == PDFUAFlavour(1, "2014")


def test_from_xmp_returns_none_when_part_missing() -> None:
    # A pdfuaid schema with rev but no part is malformed; treat as
    # "no detectable flavour".
    meta = XMPMetadata.create_xmp_metadata()
    schema = meta.add_pdfua_identification_schema()
    assert isinstance(schema, PDFUAIdentificationSchema)
    schema.set_revision("2014")
    assert PDFUAFlavour.from_xmp(meta) is None


# ---------------------------------------------------------------------------
# from_document
# ---------------------------------------------------------------------------


def test_from_document_returns_none_when_no_metadata_stream() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        assert PDFUAFlavour.from_document(doc) is None
    finally:
        doc.close()


def test_from_document_reads_pdfua_1_from_xmp_packet() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.set_metadata(PDMetadata(_xmp_packet(1)))

        flavour = PDFUAFlavour.from_document(doc)
        assert flavour == PDFUAFlavour(1)
    finally:
        doc.close()


def test_from_document_reads_part_and_rev_together() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.set_metadata(PDMetadata(_xmp_packet(1, rev="2014")))

        flavour = PDFUAFlavour.from_document(doc)
        assert flavour == PDFUAFlavour(1, "2014")
    finally:
        doc.close()


def test_from_document_returns_none_when_xmp_lacks_pdfuaid() -> None:
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

        assert PDFUAFlavour.from_document(doc) is None
    finally:
        doc.close()


def test_from_document_returns_none_for_malformed_xmp() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()
        catalog.set_metadata(PDMetadata(b"this is not XML at all"))

        # Malformed packet -> no flavour, not a crash. A passive detector
        # should never raise on bad metadata.
        assert PDFUAFlavour.from_document(doc) is None
    finally:
        doc.close()

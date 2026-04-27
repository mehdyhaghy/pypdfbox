from __future__ import annotations

from pypdfbox.xmpbox import (
    DomXmpParser,
    PDFAIdentificationSchema,
    XMPMetadata,
)


def _ident() -> PDFAIdentificationSchema:
    return PDFAIdentificationSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _ident()
    assert PDFAIdentificationSchema.NAMESPACE == "http://www.aiim.org/pdfa/ns/id/"
    assert PDFAIdentificationSchema.PREFERRED_PREFIX == "pdfaid"
    assert schema.get_namespace() == "http://www.aiim.org/pdfa/ns/id/"
    assert schema.get_prefix() == "pdfaid"


def test_default_accessors_return_none() -> None:
    schema = _ident()
    assert schema.get_part() is None
    assert schema.get_conformance() is None
    assert schema.get_amendment() is None
    assert schema.get_revision() is None
    assert schema.get_correction() is None


def test_round_trip_each_accessor() -> None:
    schema = _ident()
    schema.set_part(2)
    schema.set_conformance("B")
    schema.set_amendment("2014")
    schema.set_revision("2020")
    schema.set_correction("2021")
    assert schema.get_part() == 2
    assert schema.get_conformance() == "B"
    assert schema.get_amendment() == "2014"
    assert schema.get_revision() == "2020"
    assert schema.get_correction() == "2021"

    # set_*(None) clears the property.
    schema.set_conformance(None)
    schema.set_amendment(None)
    schema.set_revision(None)
    schema.set_correction(None)
    assert schema.get_conformance() is None
    assert schema.get_amendment() is None
    assert schema.get_revision() is None
    assert schema.get_correction() is None


def test_pdfa_part2_b_round_trips_through_xmp_packet() -> None:
    # Hand-rolled XMP packet — exercises the parser path: integers come back
    # from XML as text and ``get_part`` must coerce.
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:pdfaid='http://www.aiim.org/pdfa/ns/id/'"
        b" pdfaid:part='2' pdfaid:conformance='B'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(PDFAIdentificationSchema)
    assert isinstance(schema, PDFAIdentificationSchema)
    assert schema.get_part() == 2
    assert schema.get_conformance() == "B"
    # The convenience accessor finds the same schema instance.
    assert metadata.get_pdf_identification_schema() is schema


def test_pdfa_4_amendment_round_trips() -> None:
    schema = _ident()
    schema.set_part(4)
    schema.set_amendment("2014")
    assert schema.get_part() == 4
    assert schema.get_amendment() == "2014"
    # PDF/A 4 typically omits conformance — verify default stays None.
    assert schema.get_conformance() is None


def test_part_handles_string_storage_from_parser() -> None:
    # Simulate the parser path explicitly: attribute-form properties land
    # as raw strings via ``set_text_property_value``.
    schema = _ident()
    schema.set_text_property_value(PDFAIdentificationSchema.PART, "3")
    assert schema.get_part() == 3
    # Non-numeric garbage returns None rather than raising.
    schema.set_text_property_value(PDFAIdentificationSchema.PART, "not-a-number")
    assert schema.get_part() is None

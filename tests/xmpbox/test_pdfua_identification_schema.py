from __future__ import annotations

from pypdfbox.xmpbox import (
    DomXmpParser,
    PDFUAIdentificationSchema,
    XMPMetadata,
)


def _ident() -> PDFUAIdentificationSchema:
    return PDFUAIdentificationSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix() -> None:
    schema = _ident()
    assert PDFUAIdentificationSchema.NAMESPACE == "http://www.aiim.org/pdfua/ns/id/"
    assert PDFUAIdentificationSchema.PREFERRED_PREFIX == "pdfuaid"
    assert schema.get_namespace() == "http://www.aiim.org/pdfua/ns/id/"
    assert schema.get_prefix() == "pdfuaid"


def test_default_accessors_return_none() -> None:
    schema = _ident()
    assert schema.get_part() is None
    assert schema.get_conformance() is None
    assert schema.get_revision() is None
    assert schema.get_amendment() is None


def test_round_trip_each_accessor() -> None:
    schema = _ident()
    schema.set_part(1)
    schema.set_conformance("Acc")
    schema.set_revision("2014")
    schema.set_amendment("A1")
    assert schema.get_part() == 1
    assert schema.get_conformance() == "Acc"
    assert schema.get_revision() == "2014"
    assert schema.get_amendment() == "A1"

    # set_*(None) clears the property.
    schema.set_conformance(None)
    schema.set_revision(None)
    schema.set_amendment(None)
    assert schema.get_conformance() is None
    assert schema.get_revision() is None
    assert schema.get_amendment() is None


def test_part_handles_string_storage_from_parser() -> None:
    # Simulate the parser path explicitly: attribute-form properties land
    # as raw strings via ``set_text_property_value``.
    schema = _ident()
    schema.set_text_property_value(PDFUAIdentificationSchema.PART, "1")
    assert schema.get_part() == 1
    # Non-numeric garbage returns None rather than raising.
    schema.set_text_property_value(PDFUAIdentificationSchema.PART, "not-a-number")
    assert schema.get_part() is None


def test_pdfua_part1_round_trips_through_xmp_packet() -> None:
    # Hand-rolled XMP packet — exercises the parser path, including the
    # registry dispatch in DomXmpParser.
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:pdfuaid='http://www.aiim.org/pdfua/ns/id/'"
        b" pdfuaid:part='1'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(PDFUAIdentificationSchema)
    assert isinstance(schema, PDFUAIdentificationSchema)
    assert schema.get_part() == 1
    # The convenience accessor finds the same schema instance.
    assert metadata.get_pdfua_identification_schema() is schema


def test_pdfua_packet_with_conformance_and_rev_round_trips() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:pdfuaid='http://www.aiim.org/pdfua/ns/id/'"
        b" pdfuaid:part='1' pdfuaid:conformance='Acc' pdfuaid:rev='2014'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(PDFUAIdentificationSchema)
    assert isinstance(schema, PDFUAIdentificationSchema)
    assert schema.get_part() == 1
    assert schema.get_conformance() == "Acc"
    assert schema.get_revision() == "2014"


def test_xmp_metadata_add_is_idempotent() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    a = meta.add_pdfua_identification_schema()
    b = meta.add_pdfua_identification_schema()
    # Idempotent add — second call returns the same instance.
    assert a is b
    assert isinstance(a, PDFUAIdentificationSchema)
    assert meta.get_pdfua_identification_schema() is a

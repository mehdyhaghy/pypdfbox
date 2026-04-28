from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    BadFieldValueException,
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


# ---------- PDF/UA-2 (ISO 14289-2) round-out ----------


def test_part_constants_match_iso_parts() -> None:
    assert PDFUAIdentificationSchema.PART_1 == 1
    assert PDFUAIdentificationSchema.PART_2 == 2


def test_pdfua_part2_round_trip_with_rev() -> None:
    schema = _ident()
    schema.set_part(PDFUAIdentificationSchema.PART_2)
    schema.set_rev("2024")
    assert schema.get_part() == 2
    assert schema.get_rev() == "2024"
    assert schema.get_revision() == "2024"


def test_pdfua_part2_set_rev_accepts_int() -> None:
    schema = _ident()
    schema.set_part(PDFUAIdentificationSchema.PART_2)
    schema.set_rev(2024)
    # int input is coerced to decimal string for upstream-style round-trip.
    assert schema.get_rev() == "2024"
    assert schema.get_revision() == "2024"


def test_pdfua_part2_set_rev_none_clears() -> None:
    schema = _ident()
    schema.set_rev("2024")
    assert schema.get_rev() == "2024"
    schema.set_rev(None)
    assert schema.get_rev() is None


def test_pdfua_part2_amd_corr_round_trip() -> None:
    schema = _ident()
    schema.set_part(2)
    schema.set_amd("A1")
    schema.set_corr("Cor1:2025")
    assert schema.get_amd() == "A1"
    assert schema.get_amendment() == "A1"
    assert schema.get_corr() == "Cor1:2025"
    assert schema.get_correction() == "Cor1:2025"
    schema.set_corr(None)
    assert schema.get_corr() is None
    assert schema.get_correction() is None


def test_pdfua_part2_packet_round_trips_through_parser() -> None:
    # Realistic PDF/UA-2 XMP packet — part=2 + rev=2024 is the minimum claim.
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:pdfuaid='http://www.aiim.org/pdfua/ns/id/'"
        b" pdfuaid:part='2' pdfuaid:rev='2024'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(PDFUAIdentificationSchema)
    assert isinstance(schema, PDFUAIdentificationSchema)
    assert schema.get_part() == 2
    assert schema.get_rev() == "2024"


def test_pdfua_part2_packet_with_amd_and_corr() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:pdfuaid='http://www.aiim.org/pdfua/ns/id/'"
        b" pdfuaid:part='2' pdfuaid:rev='2024'"
        b" pdfuaid:amd='A1' pdfuaid:corr='Cor1:2025'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(PDFUAIdentificationSchema)
    assert isinstance(schema, PDFUAIdentificationSchema)
    assert schema.get_part() == 2
    assert schema.get_rev() == "2024"
    assert schema.get_amendment() == "A1"
    assert schema.get_correction() == "Cor1:2025"


def test_set_part_value_with_int_and_string_aliases() -> None:
    schema = _ident()
    schema.set_part_value_with_int(2)
    assert schema.get_part() == 2
    schema.set_part_value_with_string("1")
    assert schema.get_part() == 1

    with pytest.raises(ValueError):
        schema.set_part_value_with_string("not-a-number")


# ---------- ISO 14289 conformance validation ----------


@pytest.mark.parametrize("value", ["A", "B", "U", "Acc"])
def test_set_conformance_accepts_valid_values(value: str) -> None:
    schema = _ident()
    schema.set_conformance(value)
    assert schema.get_conformance() == value


def test_set_conformance_rejects_invalid_value() -> None:
    schema = _ident()
    with pytest.raises(BadFieldValueException):
        schema.set_conformance("Z")


def test_set_conformance_rejects_lowercase() -> None:
    # Lowercase "a"/"b"/"u" are *not* in the ISO 14289-2 value space —
    # only uppercase A/B/U (plus the legacy "Acc" spelling) are accepted.
    schema = _ident()
    with pytest.raises(BadFieldValueException):
        schema.set_conformance("a")


def test_set_conformance_none_clears_property() -> None:
    schema = _ident()
    schema.set_conformance("U")
    schema.set_conformance(None)
    assert schema.get_conformance() is None


def test_bad_field_value_exception_subclasses_value_error() -> None:
    """Callers that aren't aware of the upstream class can still
    ``except ValueError``."""
    schema = _ident()
    with pytest.raises(ValueError):
        schema.set_conformance("nope")


# ---------- ISO 14289 part predicates ----------


def test_is_pdf_ua_1_when_part_is_one() -> None:
    schema = _ident()
    schema.set_part(1)
    assert schema.is_pdf_ua_1()
    assert not schema.is_pdf_ua_2()
    assert schema.is_known_part()


def test_is_pdf_ua_2_when_part_is_two() -> None:
    schema = _ident()
    schema.set_part(2)
    assert schema.is_pdf_ua_2()
    assert not schema.is_pdf_ua_1()
    assert schema.is_known_part()


def test_predicates_default_false_when_part_absent() -> None:
    schema = _ident()
    assert not schema.is_pdf_ua_1()
    assert not schema.is_pdf_ua_2()
    assert not schema.is_known_part()


def test_is_known_part_false_for_future_part() -> None:
    schema = _ident()
    schema.set_part(99)
    assert not schema.is_known_part()
    assert not schema.is_pdf_ua_1()
    assert not schema.is_pdf_ua_2()


def test_get_part_value_alias() -> None:
    """``get_part_value`` mirrors the upstream PDF/A shape."""
    schema = _ident()
    schema.set_part(2)
    assert schema.get_part_value() == 2


def test_set_part_property_alias() -> None:
    """``set_part_property`` is an upstream-API alias of :meth:`set_part`."""
    schema = _ident()
    schema.set_part_property(2)
    assert schema.get_part() == 2

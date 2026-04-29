from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    BadFieldValueException,
    DomXmpParser,
    IntegerType,
    PDFAIdentificationSchema,
    TextType,
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


# ---------- upstream-shaped aliases ----------


def test_get_amd_alias_matches_get_amendment() -> None:
    schema = _ident()
    schema.set_amd("2014")
    assert schema.get_amd() == "2014"
    assert schema.get_amendment() == "2014"


def test_get_corr_alias_matches_get_correction() -> None:
    schema = _ident()
    schema.set_corr("2021")
    assert schema.get_corr() == "2021"
    assert schema.get_correction() == "2021"


def test_get_rev_returns_int() -> None:
    """Upstream ``getRev()`` returns an Integer post-PDFBOX-6088."""
    schema = _ident()
    schema.set_rev(2020)
    assert schema.get_rev() == 2020
    # The string-flavoured accessor still works for back-compat callers.
    assert schema.get_revision() == "2020"


def test_set_rev_value_with_string_parses_int() -> None:
    schema = _ident()
    schema.set_rev_value_with_string("2021")
    assert schema.get_rev() == 2021


def test_set_rev_value_with_string_rejects_garbage() -> None:
    schema = _ident()
    with pytest.raises(ValueError):
        schema.set_rev_value_with_string("nope")


def test_set_part_value_with_int_alias() -> None:
    schema = _ident()
    schema.set_part_value_with_int(2)
    assert schema.get_part() == 2


def test_set_part_value_with_string_parses_int() -> None:
    schema = _ident()
    schema.set_part_value_with_string("3")
    assert schema.get_part() == 3


def test_set_part_value_with_string_rejects_garbage() -> None:
    """Mirrors upstream ``IllegalArgumentException``."""
    schema = _ident()
    with pytest.raises(ValueError):
        schema.set_part_value_with_string("ojoj")


def test_typed_property_getters_rehydrate_simple_values() -> None:
    schema = _ident()
    schema.set_part(2)
    schema.set_amd("2014")
    schema.set_conformance("B")
    schema.set_rev(2020)

    part = schema.get_part_property()
    amd = schema.get_amd_property()
    conformance = schema.get_conformance_property()
    rev = schema.get_rev_property()

    assert isinstance(part, IntegerType)
    assert part.get_property_name() == PDFAIdentificationSchema.PART
    assert part.get_string_value() == "2"
    assert part.get_namespace() == PDFAIdentificationSchema.NAMESPACE
    assert part.get_prefix() == PDFAIdentificationSchema.PREFERRED_PREFIX

    assert isinstance(amd, TextType)
    assert amd.get_property_name() == PDFAIdentificationSchema.AMD
    assert amd.get_string_value() == "2014"

    assert isinstance(conformance, TextType)
    assert conformance.get_property_name() == PDFAIdentificationSchema.CONFORMANCE
    assert conformance.get_string_value() == "B"

    assert isinstance(rev, IntegerType)
    assert rev.get_property_name() == PDFAIdentificationSchema.REV
    assert rev.get_string_value() == "2020"


def test_typed_property_setters_interoperate_with_value_getters() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PDFAIdentificationSchema(metadata)
    part = IntegerType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", 3)
    amd = TextType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "2011")
    conformance = TextType(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "U"
    )
    rev = IntegerType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", 2020)

    schema.set_part_property(part)
    schema.set_amd_property(amd)
    schema.set_conformance_property(conformance)
    schema.set_rev_property(rev)

    assert schema.get_part_property() is part
    assert schema.get_amd_property() is amd
    assert schema.get_conformance_property() is conformance
    assert schema.get_rev_property() is rev
    assert [part.get_property_name(), amd.get_property_name()] == ["part", "amd"]
    assert [conformance.get_property_name(), rev.get_property_name()] == [
        "conformance",
        "rev",
    ]
    assert schema.get_part() == 3
    assert schema.get_amd() == "2011"
    assert schema.get_conformance() == "U"
    assert schema.get_rev() == 2020
    assert schema.get_revision() == "2020"

    schema.set_part_property(None)
    schema.set_amd_property(None)
    schema.set_conformance_property(None)
    schema.set_rev_property(None)

    assert schema.get_part_property() is None
    assert schema.get_amd_property() is None
    assert schema.get_conformance_property() is None
    assert schema.get_rev_property() is None
    assert schema.get_part() is None
    assert schema.get_amd() is None
    assert schema.get_conformance() is None
    assert schema.get_rev() is None


def test_conformance_property_rejects_invalid_value() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PDFAIdentificationSchema(metadata)
    prop = TextType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "Z")
    with pytest.raises(BadFieldValueException):
        schema.set_conformance_property(prop)


# ---------- conformance validation (PDFBOX-6088) ----------


@pytest.mark.parametrize("value", ["A", "B", "U", "e", "f"])
def test_set_conformance_accepts_valid_values(value: str) -> None:
    schema = _ident()
    schema.set_conformance(value)
    assert schema.get_conformance() == value


def test_set_conformance_rejects_invalid_value() -> None:
    schema = _ident()
    with pytest.raises(BadFieldValueException):
        schema.set_conformance("Z")


def test_set_conformance_none_clears_property() -> None:
    schema = _ident()
    schema.set_conformance("B")
    schema.set_conformance(None)
    assert schema.get_conformance() is None


def test_bad_field_value_exception_subclasses_value_error() -> None:
    """Callers that aren't aware of the upstream class can still
    ``except ValueError``."""
    schema = _ident()
    with pytest.raises(ValueError):
        schema.set_conformance("nope")

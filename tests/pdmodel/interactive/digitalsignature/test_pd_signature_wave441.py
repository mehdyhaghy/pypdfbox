from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.digitalsignature import PDPropBuild, PDSignature

_BYTE_RANGE = COSName.get_pdf_name("ByteRange")
_CERT = COSName.get_pdf_name("Cert")
_CONTENTS = COSName.get_pdf_name("Contents")
_PROP_BUILD = COSName.get_pdf_name("Prop_Build")


def test_setters_with_none_remove_entries_and_presence_flags() -> None:
    sig = PDSignature()
    prop_build = PDPropBuild()

    sig.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
    sig.set_name("Alice")
    sig.set_reason("Approved")
    sig.set_location("Chicago")
    sig.set_contact_info("alice@example.test")
    sig.set_sign_date("D:20260508120000Z")
    sig.set_byte_range([0, 4, 8, 4])
    sig.set_contents(b"pkcs7")
    sig.set_cert(["leaf", "issuer"])
    sig.set_prop_build(prop_build)

    assert sig.has_filter()
    assert sig.has_sub_filter()
    assert sig.has_name()
    assert sig.has_reason()
    assert sig.has_location()
    assert sig.has_contact_info()
    assert sig.has_sign_date()
    assert sig.has_byte_range()
    assert sig.has_contents()
    assert sig.has_cert()
    assert sig.has_prop_build()

    sig.set_filter(None)
    sig.set_sub_filter(None)
    sig.set_name(None)
    sig.set_reason(None)
    sig.set_location(None)
    sig.set_contact_info(None)
    sig.set_sign_date(None)
    sig.set_byte_range(None)
    sig.set_contents(None)
    sig.set_cert(None)
    sig.set_prop_build(None)

    assert sig.get_filter() is None
    assert sig.get_sub_filter() is None
    assert sig.get_name() is None
    assert sig.get_reason() is None
    assert sig.get_location() is None
    assert sig.get_contact_info() is None
    assert sig.get_sign_date() is None
    assert sig.get_byte_range() is None
    assert sig.get_contents() is None
    assert sig.get_cert() is None
    assert sig.get_prop_build() is None
    assert not sig.has_filter()
    assert not sig.has_sub_filter()
    assert not sig.has_name()
    assert not sig.has_reason()
    assert not sig.has_location()
    assert not sig.has_contact_info()
    assert not sig.has_sign_date()
    assert not sig.has_byte_range()
    assert not sig.has_contents()
    assert not sig.has_cert()
    assert not sig.has_prop_build()


def test_get_byte_range_returns_none_for_wrong_cos_shapes() -> None:
    sig = PDSignature()
    sig.get_cos_object().set_item(_BYTE_RANGE, COSName.get_pdf_name("NotArray"))
    assert sig.get_byte_range() is None

    byte_range = COSArray()
    byte_range.add(COSName.get_pdf_name("not-an-int"))
    byte_range.add(COSName.get_pdf_name("still-not-an-int"))
    sig.get_cos_object().set_item(_BYTE_RANGE, byte_range)
    assert sig.get_byte_range() is None


def test_contents_are_stored_as_forced_hex_cos_string() -> None:
    sig = PDSignature()

    sig.set_contents(b"\x01\x02signature")

    raw = sig.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(raw, COSString)
    assert raw.get_bytes() == b"\x01\x02signature"
    assert raw.get_force_hex_form() is True
    assert sig.get_contents_bytes() == b"\x01\x02signature"


def test_cert_array_ignores_non_string_entries() -> None:
    sig = PDSignature()
    certs = COSArray.of_cos_strings(["leaf", "issuer"])
    certs.add(COSName.get_pdf_name("NotACertString"))
    sig.get_cos_object().set_item(_CERT, certs)

    assert sig.get_cert() == ["leaf", "issuer"]


def test_prop_build_wraps_dictionary_and_ignores_wrong_shape() -> None:
    prop_build = PDPropBuild()
    sig = PDSignature()

    sig.set_prop_build(prop_build)
    wrapped = sig.get_prop_build()

    assert wrapped is not None
    assert wrapped.get_cos_object() is prop_build.get_cos_object()

    sig.get_cos_object().set_item(_PROP_BUILD, COSName.get_pdf_name("WrongShape"))
    assert sig.get_prop_build() is None


def test_sign_date_datetime_helpers_round_trip_and_clear() -> None:
    sig = PDSignature()
    value = dt.datetime(2026, 5, 8, 14, 30, 45, tzinfo=dt.UTC)

    sig.set_sign_date_as_datetime(value)

    assert sig.get_sign_date() == "D:20260508143045Z00'00'"
    assert sig.get_sign_date_as_datetime() == value

    sig.set_sign_date("not-a-pdf-date")
    assert sig.get_sign_date_as_datetime() is None

    sig.set_sign_date_as_datetime(None)
    assert sig.get_sign_date() is None


@pytest.mark.parametrize(
    ("sub_filter", "predicate"),
    [
        (PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED, "is_pkcs7_detached"),
        (PDSignature.SUBFILTER_ADBE_PKCS7_SHA1, "is_pkcs7_sha1"),
        (PDSignature.SUBFILTER_ADBE_X509_RSA_SHA1, "is_x509_rsa_sha1"),
        (PDSignature.SUBFILTER_ETSI_CADES_DETACHED, "is_etsi_cades_detached"),
        (PDSignature.SUBFILTER_ETSI_RFC3161, "is_etsi_rfc3161"),
    ],
)
def test_subfilter_predicates_match_exact_values(
    sub_filter: str, predicate: str
) -> None:
    sig = PDSignature()
    sig.set_sub_filter(sub_filter)

    assert getattr(sig, predicate)() is True


def test_type_predicates_distinguish_signature_and_timestamp() -> None:
    sig = PDSignature()
    assert sig.is_signature() is True
    assert sig.is_doc_time_stamp() is False

    sig.set_type(PDSignature.TYPE_DOC_TIME_STAMP)
    assert sig.is_signature() is False
    assert sig.is_doc_time_stamp() is True


def test_string_summary_omits_empty_fields() -> None:
    sig = PDSignature()
    assert str(sig) == "PDSignature(<empty>)"

    sig.set_name("Alice")
    sig.set_reason("")
    sig.set_location("Chicago")

    assert str(sig) == "PDSignature(name=Alice, location=Chicago)"


def test_verify_reports_missing_contents_after_valid_byte_range() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])

    result = sig.verify(b"AAAAxxxxBBBB")

    assert result.is_valid is False
    assert result.errors == ["missing /Contents"]
    assert result.computed_digest is None


def test_verify_reports_pkcs7_parse_failure_and_sets_sha1_digest() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_SHA1)
    sig.set_contents(b"not-pkcs7\x00\x00")

    result = sig.verify(b"AAAAxxxxBBBB")

    assert result.is_valid is False
    assert result.computed_digest is not None
    assert len(result.computed_digest) == 20
    assert result.errors
    assert result.errors[0].startswith("failed to parse PKCS#7 /Contents")


def test_get_signed_data_rejects_ranges_beyond_document_end() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 12, 1])

    assert sig.get_signed_data(b"AAAAxxxxBBBB") is None


def test_wrapping_existing_dictionary_does_not_add_type() -> None:
    backing = COSDictionary()
    sig = PDSignature(backing)

    assert sig.get_cos_object() is backing
    assert sig.get_type() is None

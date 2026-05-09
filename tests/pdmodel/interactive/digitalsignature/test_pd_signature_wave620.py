from __future__ import annotations

import datetime as dt

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature

_CERT = COSName.get_pdf_name("Cert")
_CONTENTS = COSName.get_pdf_name("Contents")


def test_verify_reports_missing_byte_range_before_contents_lookup() -> None:
    sig = PDSignature()
    sig.set_contents(b"not inspected")

    result = sig.verify(b"AAAAxxxxBBBB")

    assert result.is_valid is False
    assert result.errors == ["missing /ByteRange"]
    assert result.computed_digest is None


def test_verify_uses_sha256_digest_for_non_sha1_subfilters() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
    sig.set_contents(b"not-pkcs7\x00\x00")

    result = sig.verify(b"AAAAxxxxBBBB")

    assert result.is_valid is False
    assert result.computed_digest is not None
    assert len(result.computed_digest) == 32
    assert result.errors[0].startswith("failed to parse PKCS#7 /Contents")


def test_signed_data_allows_empty_ranges() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 0, 12, 0])

    assert sig.get_signed_data(b"AAAAxxxxBBBB") == b""
    assert sig.get_signed_content(b"AAAAxxxxBBBB") == b""


def test_naive_datetime_sign_date_is_stored_as_utc() -> None:
    sig = PDSignature()

    sig.set_sign_date_as_datetime(dt.datetime(2026, 5, 8, 14, 30, 45))

    assert sig.get_sign_date() == "D:20260508143045Z00'00'"
    assert sig.get_sign_date_as_datetime() == dt.datetime(
        2026, 5, 8, 14, 30, 45, tzinfo=dt.UTC
    )


def test_string_summary_includes_all_identity_fields_in_order() -> None:
    sig = PDSignature()
    sig.set_name("Alice")
    sig.set_reason("Approved")
    sig.set_location("Chicago")
    sig.set_sign_date("D:20260508143045Z")
    sig.set_contact_info("alice@example.test")

    assert str(sig) == (
        "PDSignature(name=Alice, reason=Approved, location=Chicago, "
        "date=D:20260508143045Z, contact=alice@example.test)"
    )


def test_wrong_cos_shapes_for_contents_and_cert_return_none() -> None:
    sig = PDSignature()
    sig.get_cos_object().set_item(_CONTENTS, COSName.get_pdf_name("NotBytes"))
    sig.get_cos_object().set_item(_CERT, COSName.get_pdf_name("NotCert"))

    assert sig.get_contents() is None
    assert sig.get_contents_bytes() is None
    assert sig.get_cert() is None


def test_filter_and_subfilter_presence_track_name_setters() -> None:
    sig = PDSignature()

    sig.set_filter(PDSignature.FILTER_ENTRUST_PPKEF)
    sig.set_sub_filter(PDSignature.SUBFILTER_ETSI_RFC3161)
    assert sig.has_filter() is True
    assert sig.has_sub_filter() is True

    sig.set_filter(None)
    sig.set_sub_filter(None)
    assert sig.has_filter() is False
    assert sig.has_sub_filter() is False

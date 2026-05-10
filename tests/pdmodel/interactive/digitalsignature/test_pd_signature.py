from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSeedValue,
    PDSignature,
    PDSignatureLock,
)

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]


def test_pd_signature_fresh_has_type_sig() -> None:
    sig = PDSignature()
    assert sig.get_cos_object().get_name(_TYPE) == "Sig"


def test_pd_signature_round_trip_filter_subfilter_name_reason() -> None:
    sig = PDSignature()
    sig.set_filter("Adobe.PPKLite")
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_name("Alice Example")
    sig.set_reason("I approve this document")

    assert sig.get_filter() == "Adobe.PPKLite"
    assert sig.get_sub_filter() == "adbe.pkcs7.detached"
    assert sig.get_name() == "Alice Example"
    assert sig.get_reason() == "I approve this document"


def test_pd_signature_byte_range_round_trip() -> None:
    sig = PDSignature()
    assert sig.get_byte_range() is None
    sig.set_byte_range([0, 100, 200, 50])
    assert sig.get_byte_range() == [0, 100, 200, 50]


def test_pd_signature_optional_fields_default_none() -> None:
    sig = PDSignature()
    assert sig.get_filter() is None
    assert sig.get_sub_filter() is None
    assert sig.get_name() is None
    assert sig.get_location() is None
    assert sig.get_reason() is None
    assert sig.get_contact_info() is None
    assert sig.get_sign_date() is None
    assert sig.get_contents() is None


def test_pd_seed_value_fresh_has_type_sv() -> None:
    sv = PDSeedValue()
    assert sv.get_cos_object().get_name(_TYPE) == "SV"


def test_pd_seed_value_sub_filter_round_trip() -> None:
    sv = PDSeedValue()
    sv.set_sub_filter(["adbe.pkcs7.detached", "ETSI.CAdES.detached"])
    assert sv.get_sub_filter() == ["adbe.pkcs7.detached", "ETSI.CAdES.detached"]

    sv.set_v(2)
    assert sv.get_v() == 2

    sv.set_reasons(["personal", "legal"])
    assert sv.get_reasons() == ["personal", "legal"]


def test_pd_signature_lock_fresh_has_type_sig_field_lock() -> None:
    lock = PDSignatureLock()
    assert lock.get_cos_object().get_name(_TYPE) == "SigFieldLock"


def test_pd_signature_lock_round_trip_action_and_fields() -> None:
    lock = PDSignatureLock()
    lock.set_action("Include")
    lock.set_fields(["sig1", "sig2"])

    assert lock.get_action() == "Include"
    assert lock.get_fields() == ["sig1", "sig2"]

    lock.set_p(2)
    assert lock.get_p() == 2


def test_pd_signature_lock_action_constants_match_pdf_spec() -> None:
    """PDF 32000-1 §12.7.4.5 Table 233 SigFieldLock /Action values."""
    assert PDSignatureLock.ACTION_ALL == "All"
    assert PDSignatureLock.ACTION_INCLUDE == "Include"
    assert PDSignatureLock.ACTION_EXCLUDE == "Exclude"


def test_pd_signature_lock_action_constants_round_trip() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_ALL)
    assert lock.get_action() == "All"
    lock.set_action(PDSignatureLock.ACTION_INCLUDE)
    assert lock.get_action() == "Include"
    lock.set_action(PDSignatureLock.ACTION_EXCLUDE)
    assert lock.get_action() == "Exclude"


def test_pd_signature_lock_p_permission_constants_match_pdf_spec() -> None:
    """PDF 32000-1 §12.7.4.5 Table 233 SigFieldLock /P values."""
    assert PDSignatureLock.P_NO_CHANGES == 1
    assert PDSignatureLock.P_ALLOW_FORM_FILL == 2
    assert PDSignatureLock.P_ALLOW_FORM_FILL_AND_ANNOTATIONS == 3


def test_pd_signature_lock_p_permission_constants_round_trip() -> None:
    lock = PDSignatureLock()
    lock.set_p(PDSignatureLock.P_NO_CHANGES)
    assert lock.get_p() == 1
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL)
    assert lock.get_p() == 2
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL_AND_ANNOTATIONS)
    assert lock.get_p() == 3


# ---------------------------------------------------------------------------
# /Type, /Cert, /M accessors
# ---------------------------------------------------------------------------


def test_pd_signature_get_type_default_sig() -> None:
    sig = PDSignature()
    assert sig.get_type() == "Sig"


def test_pd_signature_set_type_round_trip_and_remove() -> None:
    sig = PDSignature()
    sig.set_type("DocTimeStamp")
    assert sig.get_type() == "DocTimeStamp"
    sig.set_type(None)
    assert sig.get_type() is None


def test_pd_signature_cert_single_string_round_trip() -> None:
    sig = PDSignature()
    assert sig.get_cert() is None
    sig.set_cert("DER-bytes-as-string")
    # Single-string storage is still surfaced as a one-element list on read.
    assert sig.get_cert() == ["DER-bytes-as-string"]


def test_pd_signature_cert_array_round_trip() -> None:
    sig = PDSignature()
    sig.set_cert(["leaf-cert", "intermediate-cert", "root-cert"])
    assert sig.get_cert() == ["leaf-cert", "intermediate-cert", "root-cert"]


def test_pd_signature_cert_set_none_removes_entry() -> None:
    sig = PDSignature()
    sig.set_cert("anything")
    sig.set_cert(None)
    assert sig.get_cert() is None
    assert not sig.get_cos_object().contains_key("Cert")


def test_pd_signature_set_sign_date_round_trip() -> None:
    sig = PDSignature()
    assert sig.get_sign_date() is None
    sig.set_sign_date("D:20260427120000Z")
    assert sig.get_sign_date() == "D:20260427120000Z"
    sig.set_sign_date(None)
    assert sig.get_sign_date() is None


def test_pd_signature_set_byte_range_rejects_wrong_length() -> None:
    import pytest

    sig = PDSignature()
    with pytest.raises(ValueError, match="exactly 4"):
        sig.set_byte_range([0, 100, 200])
    with pytest.raises(ValueError, match="exactly 4"):
        sig.set_byte_range([0, 100, 200, 300, 400])


# ---------------------------------------------------------------------------
# Filter / SubFilter constants and getNameAsString-equivalent behavior
# ---------------------------------------------------------------------------


def test_pd_signature_filter_constants_match_pdf_table_252() -> None:
    """The four /Filter constants are spec values from PDF 32000-1 Table 252."""
    assert PDSignature.FILTER_ADOBE_PPKLITE == "Adobe.PPKLite"
    assert PDSignature.FILTER_ENTRUST_PPKEF == "Entrust.PPKEF"
    assert PDSignature.FILTER_CICI_SIGNIT == "CICI.SignIt"
    assert PDSignature.FILTER_VERISIGN_PPKVS == "VeriSign.PPKVS"


def test_pd_signature_subfilter_constants_match_pdf_table_252() -> None:
    """The four /SubFilter constants are spec values from PDF 32000-1 Table 252."""
    assert PDSignature.SUBFILTER_ADBE_X509_RSA_SHA1 == "adbe.x509.rsa_sha1"
    assert PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED == "adbe.pkcs7.detached"
    assert PDSignature.SUBFILTER_ETSI_CADES_DETACHED == "ETSI.CAdES.detached"
    assert PDSignature.SUBFILTER_ADBE_PKCS7_SHA1 == "adbe.pkcs7.sha1"


def test_pd_signature_filter_constants_round_trip_through_setter() -> None:
    """Constants feed cleanly into ``set_filter`` / ``set_sub_filter``."""
    sig = PDSignature()
    sig.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
    assert sig.get_filter() == "Adobe.PPKLite"
    assert sig.get_sub_filter() == "adbe.pkcs7.detached"


def test_pd_signature_get_filter_accepts_cos_string() -> None:
    """Upstream uses ``getNameAsString`` so a /Filter stored as COSString
    (non-conformant but seen in the wild) must still return its value."""
    from pypdfbox.cos import COSString

    sig = PDSignature()
    sig.get_cos_object().set_item(
        COSName.get_pdf_name("Filter"), COSString("Adobe.PPKLite")
    )
    assert sig.get_filter() == "Adobe.PPKLite"


def test_pd_signature_get_sub_filter_accepts_cos_string() -> None:
    from pypdfbox.cos import COSString

    sig = PDSignature()
    sig.get_cos_object().set_item(
        COSName.get_pdf_name("SubFilter"), COSString("adbe.pkcs7.detached")
    )
    assert sig.get_sub_filter() == "adbe.pkcs7.detached"


# ---------------------------------------------------------------------------
# get_signed_content
# ---------------------------------------------------------------------------


def test_pd_signature_get_signed_content_concatenates_byte_range_slices() -> None:
    """``get_signed_content`` returns the bytes covered by /ByteRange — i.e.
    the document with the /Contents hex placeholder excised. Mirrors
    upstream ``getSignedContent(byte[])``."""
    sig = PDSignature()
    # Doc layout: [0..10) signed, [10..18) /Contents placeholder,
    #             [18..30) signed.
    sig.set_byte_range([0, 10, 18, 12])
    pdf = bytes(range(30))
    signed = sig.get_signed_content(pdf)
    assert signed == bytes(range(10)) + bytes(range(18, 30))


def test_pd_signature_get_signed_content_raises_when_byte_range_missing() -> None:
    import pytest

    sig = PDSignature()
    with pytest.raises(IndexError):
        sig.get_signed_content(b"some pdf bytes")


# ---------------------------------------------------------------------------
# PDSeedValue.set_digest_method validation
# ---------------------------------------------------------------------------


def test_pd_seed_value_allowed_digest_names_are_spec_set() -> None:
    """Spec-defined acceptable algorithms: SHA1, SHA256, SHA384, SHA512,
    RIPEMD160 (PDF 32000-1 Table 234)."""
    assert set(PDSeedValue.ALLOWED_DIGEST_NAMES) == {
        "SHA1",
        "SHA256",
        "SHA384",
        "SHA512",
        "RIPEMD160",
    }


def test_pd_seed_value_set_digest_method_accepts_allowed_names() -> None:
    sv = PDSeedValue()
    sv.set_digest_method(["SHA1", "SHA256", "SHA384", "SHA512", "RIPEMD160"])
    assert sv.get_digest_method() == [
        "SHA1",
        "SHA256",
        "SHA384",
        "SHA512",
        "RIPEMD160",
    ]


def test_pd_seed_value_set_digest_method_rejects_disallowed_name() -> None:
    """Mirrors upstream ``IllegalArgumentException`` raised when a digest
    outside the allow-list is passed to ``setDigestMethod``."""
    import pytest

    sv = PDSeedValue()
    with pytest.raises(ValueError, match="MD5"):
        sv.set_digest_method(["SHA256", "MD5"])


def test_pd_seed_value_set_digest_method_none_removes_entry() -> None:
    sv = PDSeedValue()
    sv.set_digest_method(["SHA256"])
    sv.set_digest_method(None)
    assert sv.get_digest_method() == []
    assert not sv.get_cos_object().contains_key("DigestMethod")


# ---------------------------------------------------------------------------
# PDSignature.__str__ — parity backing for PDSignatureField.getValueAsString()
# ---------------------------------------------------------------------------


def test_pd_signature_str_empty_when_no_identity_fields() -> None:
    """An untouched signature has only ``/Type /Sig`` populated. None of the
    identity fields surface in ``__str__`` so the body is the placeholder."""
    sig = PDSignature()
    assert str(sig) == "PDSignature(<empty>)"


def test_pd_signature_str_includes_populated_identity_fields_in_order() -> None:
    sig = PDSignature()
    sig.set_name("Alice Example")
    sig.set_reason("I approve this document")
    sig.set_location("Berlin")
    sig.set_sign_date("D:20260501123000Z")
    sig.set_contact_info("alice@example.com")
    s = str(sig)
    # name then reason then location then date then contact (declaration order).
    assert s == (
        "PDSignature("
        "name=Alice Example, "
        "reason=I approve this document, "
        "location=Berlin, "
        "date=D:20260501123000Z, "
        "contact=alice@example.com"
        ")"
    )


def test_pd_signature_str_omits_absent_fields() -> None:
    sig = PDSignature()
    sig.set_name("Bob")
    # No reason / location / date / contact set.
    assert str(sig) == "PDSignature(name=Bob)"


# ---------------------------------------------------------------------------
# Wave 219: presence predicates, /Type and /SubFilter predicates,
# datetime accessors, DocTimeStamp / RFC3161 constants
# ---------------------------------------------------------------------------


def test_pd_signature_doc_time_stamp_constants_match_pdf_spec() -> None:
    """PDF 32000-2 §12.8.5 — RFC 3161 document timestamp uses
    ``/Type /DocTimeStamp`` and ``/SubFilter /ETSI.RFC3161``."""
    assert PDSignature.TYPE_DOC_TIME_STAMP == "DocTimeStamp"
    assert PDSignature.SUBFILTER_ETSI_RFC3161 == "ETSI.RFC3161"


def test_pd_signature_type_constants_round_trip_through_setter() -> None:
    sig = PDSignature()
    sig.set_type(PDSignature.TYPE_DOC_TIME_STAMP)
    assert sig.get_type() == "DocTimeStamp"
    sig.set_type(PDSignature.TYPE)
    assert sig.get_type() == "Sig"


# --- presence predicates ---


def test_pd_signature_presence_predicates_default_false() -> None:
    """A fresh signature has only ``/Type /Sig`` populated."""
    sig = PDSignature()
    assert sig.has_filter() is False
    assert sig.has_sub_filter() is False
    assert sig.has_byte_range() is False
    assert sig.has_contents() is False
    assert sig.has_cert() is False
    assert sig.has_prop_build() is False
    assert sig.has_sign_date() is False
    assert sig.has_name() is False
    assert sig.has_reason() is False
    assert sig.has_location() is False
    assert sig.has_contact_info() is False


def test_pd_signature_presence_predicates_true_after_set() -> None:
    sig = PDSignature()
    sig.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
    sig.set_byte_range([0, 10, 18, 12])
    sig.set_contents(b"\x30\x82\x00\x00")
    sig.set_cert("cert-bytes")
    sig.set_sign_date("D:20260501120000Z")
    sig.set_name("Alice")
    sig.set_reason("I approve")
    sig.set_location("Berlin")
    sig.set_contact_info("alice@example.com")

    assert sig.has_filter() is True
    assert sig.has_sub_filter() is True
    assert sig.has_byte_range() is True
    assert sig.has_contents() is True
    assert sig.has_cert() is True
    assert sig.has_sign_date() is True
    assert sig.has_name() is True
    assert sig.has_reason() is True
    assert sig.has_location() is True
    assert sig.has_contact_info() is True


def test_pd_signature_has_prop_build_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.digitalsignature import PDPropBuild

    sig = PDSignature()
    assert sig.has_prop_build() is False
    sig.set_prop_build(PDPropBuild())
    assert sig.has_prop_build() is True
    sig.set_prop_build(None)
    assert sig.has_prop_build() is False


def test_pd_signature_presence_predicates_false_after_clear() -> None:
    """Setting any field to ``None`` removes the entry; predicate flips back."""
    sig = PDSignature()
    sig.set_filter("Adobe.PPKLite")
    assert sig.has_filter() is True
    sig.set_filter(None)
    assert sig.has_filter() is False

    sig.set_byte_range([0, 1, 2, 3])
    assert sig.has_byte_range() is True
    sig.set_byte_range(None)
    assert sig.has_byte_range() is False


# --- /Type predicates ---


def test_pd_signature_is_signature_default_true() -> None:
    """Fresh signature has ``/Type /Sig``."""
    sig = PDSignature()
    assert sig.is_signature() is True
    assert sig.is_doc_time_stamp() is False


def test_pd_signature_is_doc_time_stamp_when_type_is_doc_time_stamp() -> None:
    sig = PDSignature()
    sig.set_type(PDSignature.TYPE_DOC_TIME_STAMP)
    assert sig.is_doc_time_stamp() is True
    assert sig.is_signature() is False


def test_pd_signature_type_predicates_both_false_when_type_absent() -> None:
    sig = PDSignature()
    sig.set_type(None)
    assert sig.is_signature() is False
    assert sig.is_doc_time_stamp() is False


# --- /SubFilter predicates ---


def test_pd_signature_subfilter_predicates_default_false() -> None:
    sig = PDSignature()
    assert sig.is_pkcs7_detached() is False
    assert sig.is_pkcs7_sha1() is False
    assert sig.is_x509_rsa_sha1() is False
    assert sig.is_etsi_cades_detached() is False
    assert sig.is_etsi_rfc3161() is False


def test_pd_signature_is_pkcs7_detached_only_when_subfilter_matches() -> None:
    sig = PDSignature()
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
    assert sig.is_pkcs7_detached() is True
    assert sig.is_pkcs7_sha1() is False
    assert sig.is_x509_rsa_sha1() is False
    assert sig.is_etsi_cades_detached() is False
    assert sig.is_etsi_rfc3161() is False


def test_pd_signature_is_pkcs7_sha1_only_when_subfilter_matches() -> None:
    sig = PDSignature()
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_SHA1)
    assert sig.is_pkcs7_sha1() is True
    assert sig.is_pkcs7_detached() is False


def test_pd_signature_is_x509_rsa_sha1_only_when_subfilter_matches() -> None:
    sig = PDSignature()
    sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_X509_RSA_SHA1)
    assert sig.is_x509_rsa_sha1() is True
    assert sig.is_pkcs7_detached() is False
    assert sig.is_etsi_cades_detached() is False


def test_pd_signature_is_etsi_cades_detached_only_when_subfilter_matches() -> None:
    sig = PDSignature()
    sig.set_sub_filter(PDSignature.SUBFILTER_ETSI_CADES_DETACHED)
    assert sig.is_etsi_cades_detached() is True
    assert sig.is_pkcs7_detached() is False


def test_pd_signature_is_etsi_rfc3161_only_when_subfilter_matches() -> None:
    sig = PDSignature()
    sig.set_sub_filter(PDSignature.SUBFILTER_ETSI_RFC3161)
    assert sig.is_etsi_rfc3161() is True
    assert sig.is_pkcs7_detached() is False
    assert sig.is_etsi_cades_detached() is False


def test_pd_signature_subfilter_predicates_case_sensitive() -> None:
    """Predicate matching is exact; mixed-case ``/SubFilter`` does not
    match. PDF spec values are case-sensitive."""
    sig = PDSignature()
    sig.set_sub_filter("ADBE.PKCS7.DETACHED")  # not the canonical lowercase
    assert sig.is_pkcs7_detached() is False


# --- typed datetime accessors ---


def test_pd_signature_get_sign_date_as_datetime_default_none() -> None:
    sig = PDSignature()
    assert sig.get_sign_date_as_datetime() is None


def test_pd_signature_set_sign_date_as_datetime_round_trip_utc() -> None:
    import datetime as dt

    sig = PDSignature()
    when = dt.datetime(2026, 5, 1, 12, 30, 0, tzinfo=dt.UTC)
    sig.set_sign_date_as_datetime(when)
    # Stored as PDF date string.
    assert sig.get_sign_date() == "D:20260501123000Z00'00'"
    # Round-trip through the typed accessor preserves the instant.
    got = sig.get_sign_date_as_datetime()
    assert got == when


def test_pd_signature_set_sign_date_as_datetime_round_trip_with_offset() -> None:
    import datetime as dt

    sig = PDSignature()
    tz = dt.timezone(dt.timedelta(hours=5, minutes=30))
    when = dt.datetime(2026, 5, 1, 18, 0, 0, tzinfo=tz)
    sig.set_sign_date_as_datetime(when)
    assert sig.get_sign_date() == "D:20260501180000+05'30'"
    got = sig.get_sign_date_as_datetime()
    assert got is not None
    # Same instant, possibly different tzinfo representation.
    assert got == when


def test_pd_signature_set_sign_date_as_datetime_none_removes_entry() -> None:
    import datetime as dt

    sig = PDSignature()
    sig.set_sign_date_as_datetime(dt.datetime(2026, 5, 1, tzinfo=dt.UTC))
    sig.set_sign_date_as_datetime(None)
    assert sig.has_sign_date() is False
    assert sig.get_sign_date_as_datetime() is None


def test_pd_signature_get_sign_date_as_datetime_returns_none_for_unparseable() -> None:
    sig = PDSignature()
    sig.set_sign_date("not a pdf date")
    assert sig.get_sign_date_as_datetime() is None
    # The raw string is still retrievable via the string accessor.
    assert sig.get_sign_date() == "not a pdf date"


def test_pd_signature_get_sign_date_as_datetime_parses_existing_string() -> None:
    """A signature parsed from a PDF will have ``/M`` as a string already;
    the typed accessor must parse it without going through the setter."""
    import datetime as dt

    sig = PDSignature()
    sig.set_sign_date("D:20260501123000Z")
    got = sig.get_sign_date_as_datetime()
    assert got == dt.datetime(2026, 5, 1, 12, 30, 0, tzinfo=dt.UTC)

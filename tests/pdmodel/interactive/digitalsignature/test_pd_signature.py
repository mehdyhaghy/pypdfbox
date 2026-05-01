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

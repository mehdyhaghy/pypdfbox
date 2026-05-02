from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSignature,
    check_certificate_usage,
    check_responder_certificate_usage,
    check_time_stamp_certificate_usage,
    compute_byte_range,
    compute_signed_digest,
    extract_pkcs7_message_digest,
    get_last_relevant_signature,
    get_mdp_permission,
    set_mdp_permission,
)
from pypdfbox.pdmodel.pd_document import PDDocument


# ---------------------------------------------------------- cert factory


def _make_cert(
    *,
    key_usage: dict | None = None,
    key_usage_critical: bool = True,
    extended_key_usage: list[str] | None = None,
):
    """Build a self-signed leaf cert with the requested KU / EKU bits.

    Returns a ``cryptography`` ``Certificate`` object — only the extension
    bits matter for SigUtils, so this stays compact.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID, ObjectIdentifier

    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = dt.datetime.now(dt.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=1))
    )

    if key_usage is not None:
        ku_kwargs = {
            "digital_signature": False,
            "content_commitment": False,
            "key_encipherment": False,
            "data_encipherment": False,
            "key_agreement": False,
            "key_cert_sign": False,
            "crl_sign": False,
            "encipher_only": False,
            "decipher_only": False,
        }
        ku_kwargs.update(key_usage)
        builder = builder.add_extension(
            x509.KeyUsage(**ku_kwargs), critical=key_usage_critical
        )

    if extended_key_usage is not None:
        usages = [ObjectIdentifier(o) for o in extended_key_usage]
        builder = builder.add_extension(
            x509.ExtendedKeyUsage(usages), critical=False
        )

    return builder.sign(private_key, hashes.SHA256())


# ---------------------------------------------------------- check_certificate_usage


def test_check_certificate_usage_clean_cert_returns_no_warnings():
    cert = _make_cert(
        key_usage={"digital_signature": True},
        extended_key_usage=["1.3.6.1.5.5.7.3.4"],  # emailProtection
    )
    assert check_certificate_usage(cert) == []


def test_check_certificate_usage_warns_on_missing_key_usage():
    cert = _make_cert()  # no KU at all
    warnings = check_certificate_usage(cert)
    assert any("KeyUsage" in w for w in warnings)


def test_check_certificate_usage_warns_when_key_usage_not_critical():
    cert = _make_cert(
        key_usage={"digital_signature": True},
        key_usage_critical=False,
    )
    warnings = check_certificate_usage(cert)
    assert any("not marked critical" in w for w in warnings)


def test_check_certificate_usage_warns_when_signing_bits_clear():
    cert = _make_cert(key_usage={"key_encipherment": True})
    warnings = check_certificate_usage(cert)
    assert any("digitalSignature" in w for w in warnings)


def test_check_certificate_usage_accepts_non_repudiation():
    """``content_commitment`` is the v3 name for nonRepudiation."""
    cert = _make_cert(
        key_usage={"content_commitment": True},
        extended_key_usage=["1.2.840.113583.1.1.5"],  # Adobe Authentic Docs
    )
    assert check_certificate_usage(cert) == []


def test_check_certificate_usage_warns_on_bad_extended_key_usage():
    cert = _make_cert(
        key_usage={"digital_signature": True},
        extended_key_usage=["1.3.6.1.5.5.7.3.1"],  # serverAuth
    )
    warnings = check_certificate_usage(cert)
    assert any("ExtendedKeyUsage" in w for w in warnings)


def test_check_certificate_usage_no_eku_is_ok():
    """ExtendedKeyUsage is optional; absence shouldn't warn."""
    cert = _make_cert(key_usage={"digital_signature": True})
    warnings = check_certificate_usage(cert)
    assert not any("ExtendedKeyUsage" in w for w in warnings)


# -------------------------------------------------- check_responder_certificate_usage


def test_responder_cert_with_ocsp_signing_passes():
    cert = _make_cert(extended_key_usage=["1.3.6.1.5.5.7.3.9"])
    assert check_responder_certificate_usage(cert) == []


def test_responder_cert_without_eku_warns():
    cert = _make_cert()
    warnings = check_responder_certificate_usage(cert)
    assert any("ExtendedKeyUsage" in w for w in warnings)


def test_responder_cert_without_ocsp_signing_warns():
    cert = _make_cert(extended_key_usage=["1.3.6.1.5.5.7.3.4"])
    warnings = check_responder_certificate_usage(cert)
    assert any("OCSPSigning" in w for w in warnings)


# --------------------------------------------------------------- MDP API


def test_get_mdp_permission_returns_zero_for_fresh_doc():
    doc = PDDocument()
    assert get_mdp_permission(doc) == 0


def test_set_mdp_permission_round_trips():
    doc = PDDocument()
    sig = PDSignature()
    set_mdp_permission(doc, sig, 2)
    assert get_mdp_permission(doc) == 2


def test_set_mdp_permission_round_trips_p1():
    doc = PDDocument()
    sig = PDSignature()
    set_mdp_permission(doc, sig, 1)
    assert get_mdp_permission(doc) == 1


def test_set_mdp_permission_round_trips_p3():
    doc = PDDocument()
    sig = PDSignature()
    set_mdp_permission(doc, sig, 3)
    assert get_mdp_permission(doc) == 3


def test_set_mdp_permission_rejects_invalid_value():
    doc = PDDocument()
    sig = PDSignature()
    with pytest.raises(ValueError, match="1, 2 or 3"):
        set_mdp_permission(doc, sig, 4)
    with pytest.raises(ValueError, match="1, 2 or 3"):
        set_mdp_permission(doc, sig, 0)


def test_set_mdp_permission_rejects_double_install():
    doc = PDDocument()
    sig1 = PDSignature()
    sig2 = PDSignature()
    set_mdp_permission(doc, sig1, 2)
    with pytest.raises(ValueError, match="already present"):
        set_mdp_permission(doc, sig2, 1)


def test_get_mdp_permission_ignores_unknown_transform_method():
    """A SigRef with TransformMethod=FieldMDP must not be reported."""
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    perms = COSDictionary()
    sig_dict = COSDictionary()
    ref = COSDictionary()
    ref.set_item(
        COSName.get_pdf_name("TransformMethod"),
        COSName.get_pdf_name("FieldMDP"),
    )
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("P"), COSInteger.get(2))
    ref.set_item(COSName.get_pdf_name("TransformParams"), params)
    refs = COSArray()
    refs.add(ref)
    sig_dict.set_item(COSName.get_pdf_name("Reference"), refs)
    perms.set_item(COSName.get_pdf_name("DocMDP"), sig_dict)
    catalog.set_perms(perms)
    assert get_mdp_permission(doc) == 0


def test_get_mdp_permission_clamps_out_of_range_p_to_zero():
    doc = PDDocument()
    sig = PDSignature()
    set_mdp_permission(doc, sig, 2)
    # Mutate /P to an invalid value behind SigUtils' back.
    sig_dict = sig.get_cos_object()
    refs = sig_dict.get_dictionary_object(COSName.get_pdf_name("Reference"))
    ref = refs.get_object(0)
    params = ref.get_dictionary_object(COSName.get_pdf_name("TransformParams"))
    params.set_item(COSName.get_pdf_name("P"), COSInteger.get(99))
    assert get_mdp_permission(doc) == 0


# --------------------------------------------------------- get_last_relevant_signature


def _attach_signature(doc: PDDocument, byte_range: list[int] | None) -> PDSignature:
    """Attach a PDSignature value to a synthetic PDSignatureField on ``doc``."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    catalog = doc.get_document_catalog()
    acro = catalog.get_acro_form()
    if acro is None:
        acro = PDAcroForm(doc)
        catalog.set_acro_form(acro)
    field = PDSignatureField(acro)
    sig = PDSignature()
    if byte_range is not None:
        sig.set_byte_range(byte_range)
    field.set_value(sig)
    fields = acro.get_fields()
    fields.append(field)
    acro.set_fields(fields)
    return sig


def test_get_last_relevant_signature_none_when_no_signatures():
    doc = PDDocument()
    assert get_last_relevant_signature(doc) is None


def test_get_last_relevant_signature_picks_latest_byte_range():
    doc = PDDocument()
    early = _attach_signature(doc, [0, 100, 200, 50])  # ends at 250
    late = _attach_signature(doc, [0, 500, 600, 400])  # ends at 1000
    _attach_signature(doc, [0, 200, 300, 100])  # ends at 400
    chosen = get_last_relevant_signature(doc)
    assert chosen is not None
    # Wrappers are recreated per ``get_signature_dictionaries`` call, so
    # compare the underlying COS dictionary identity instead.
    assert chosen.get_cos_object() is late.get_cos_object()
    assert chosen.get_cos_object() is not early.get_cos_object()


def test_get_last_relevant_signature_falls_back_to_last_when_no_byte_range():
    doc = PDDocument()
    _attach_signature(doc, None)
    last = _attach_signature(doc, None)
    chosen = get_last_relevant_signature(doc)
    assert chosen is not None
    assert chosen.get_cos_object() is last.get_cos_object()


# ----------------------------------------------------------------- /ByteRange


def test_compute_byte_range_brackets_contents_inclusively() -> None:
    """`<` at offset 50, `>` at offset 70 of a 100-byte file:
    range1 = [0..50] (51 bytes, includes `<`),
    range2 = [70..99] (30 bytes, includes `>`)."""
    document = b"x" * 100
    br = compute_byte_range(document, 50, 70)
    assert br == [0, 51, 70, 30]


def test_compute_byte_range_at_file_extremes() -> None:
    document = b"<....>" + b"y" * 10
    # `<` at 0, `>` at 5
    br = compute_byte_range(document, 0, 5)
    assert br == [0, 1, 5, len(document) - 5]


def test_compute_byte_range_rejects_out_of_range_offsets() -> None:
    document = b"x" * 50
    with pytest.raises(ValueError, match="out of range"):
        compute_byte_range(document, 50, 60)
    with pytest.raises(ValueError, match="out of range"):
        compute_byte_range(document, -1, 10)


def test_compute_byte_range_rejects_inverted_offsets() -> None:
    document = b"x" * 50
    with pytest.raises(ValueError, match="malformed"):
        compute_byte_range(document, 30, 30)
    with pytest.raises(ValueError, match="malformed"):
        compute_byte_range(document, 30, 20)


def test_compute_signed_digest_concatenates_then_hashes() -> None:
    import hashlib

    document = b"AAAA" + b"x" * 192 + b"BBBB"  # 200 bytes
    br = [0, 4, 196, 4]
    expected = hashlib.sha256(b"AAAABBBB").digest()
    assert compute_signed_digest(document, br) == expected


def test_compute_signed_digest_supports_sha1() -> None:
    import hashlib

    document = b"HEAD" + b"x" * 92 + b"TAIL"
    br = [0, 4, 96, 4]
    expected = hashlib.sha1(b"HEADTAIL").digest()  # noqa: S324
    assert compute_signed_digest(document, br, algorithm="sha1") == expected


def test_compute_signed_digest_rejects_wrong_byte_range_size() -> None:
    with pytest.raises(ValueError, match="exactly 4"):
        compute_signed_digest(b"x" * 100, [0, 10, 90])


# ---------------------------------------------------------- DER messageDigest


def test_extract_pkcs7_message_digest_returns_none_when_oid_absent() -> None:
    assert extract_pkcs7_message_digest(b"\x00" * 64) is None


def test_extract_pkcs7_message_digest_pulls_octet_string_payload() -> None:
    """Synthesize the DER fragment a CMS signedAttr emits:

        SEQUENCE
          OBJECT IDENTIFIER messageDigest
          SET
            OCTET STRING <payload>
    """
    digest = b"\xab" * 32  # 32-byte SHA-256 result
    # OID DER for 1.2.840.113549.1.9.4
    oid_der = bytes.fromhex("06092A864886F70D010904")
    octet_string = b"\x04" + bytes([len(digest)]) + digest
    set_ = b"\x31" + bytes([len(octet_string)]) + octet_string
    blob = b"prefix-junk-bytes" + oid_der + set_ + b"trailing-junk"

    assert extract_pkcs7_message_digest(blob) == digest


def test_extract_pkcs7_message_digest_handles_long_form_lengths() -> None:
    """SHA-512 has a 64-byte output — still encodes in short form, so use
    a synthetic 200-byte value to force long-form length encoding."""
    digest = b"\xcd" * 200  # >127, forces long-form length
    oid_der = bytes.fromhex("06092A864886F70D010904")
    # OCTET STRING long-form length: tag 04, length-of-length 0x81, length 0xC8.
    octet_string = b"\x04\x81\xc8" + digest
    # SET wrapping it: tag 31, length-of-length 0x81, length = 3 + 200 = 203.
    set_ = b"\x31\x81\xcb" + octet_string
    blob = oid_der + set_

    assert extract_pkcs7_message_digest(blob) == digest


def test_extract_pkcs7_message_digest_rejects_indefinite_length() -> None:
    """DER forbids indefinite-length encoding (``80`` byte). Helper must
    treat a malformed length as 'unrecoverable' and return None rather
    than raising."""
    oid_der = bytes.fromhex("06092A864886F70D010904")
    # SET with indefinite length (0x80) — invalid DER.
    blob = oid_der + b"\x31\x80\x04\x04abcd\x00\x00"
    assert extract_pkcs7_message_digest(blob) is None


def test_extract_pkcs7_message_digest_rejects_truncated_blob() -> None:
    """If the SET length runs past EOF, return None rather than raising."""
    oid_der = bytes.fromhex("06092A864886F70D010904")
    blob = oid_der + b"\x31\xff"  # claims 255 bytes follow but they don't
    assert extract_pkcs7_message_digest(blob) is None


# ----------------------------------------------- check_time_stamp_certificate_usage


def test_time_stamp_cert_with_time_stamping_passes():
    """TSA cert carrying id-kp-timeStamping (1.3.6.1.5.5.7.3.8) is OK."""
    cert = _make_cert(extended_key_usage=["1.3.6.1.5.5.7.3.8"])
    assert check_time_stamp_certificate_usage(cert) == []


def test_time_stamp_cert_without_time_stamping_warns():
    """TSA cert with EKU but missing id-kp-timeStamping warns."""
    cert = _make_cert(extended_key_usage=["1.3.6.1.5.5.7.3.4"])
    warnings = check_time_stamp_certificate_usage(cert)
    assert any("timeStamping" in w for w in warnings)
    assert any("1.3.6.1.5.5.7.3.8" in w for w in warnings)


def test_time_stamp_cert_without_eku_is_silent():
    """Matches upstream: no EKU at all is silent (only present-but-wrong warns)."""
    cert = _make_cert()
    assert check_time_stamp_certificate_usage(cert) == []


# --------------------------------- check_certificate_usage extended OID acceptance


def test_check_certificate_usage_accepts_any_extended_key_usage():
    """anyExtendedKeyUsage (2.5.29.37.0) is accepted by upstream."""
    cert = _make_cert(
        key_usage={"digital_signature": True},
        extended_key_usage=["2.5.29.37.0"],
    )
    assert check_certificate_usage(cert) == []


def test_check_certificate_usage_accepts_microsoft_document_signing():
    """Microsoft Document Signing (1.3.6.1.4.1.311.10.3.12) is tolerated."""
    cert = _make_cert(
        key_usage={"digital_signature": True},
        extended_key_usage=["1.3.6.1.4.1.311.10.3.12"],
    )
    assert check_certificate_usage(cert) == []


# -------------------------------- set_mdp_permission approval-signature gating


def test_set_mdp_permission_rejects_when_approval_signature_present():
    """Upstream raises if any non-timestamp /Contents-bearing signature
    already exists — the certification (DocMDP) signature must precede
    approval signatures."""
    doc = PDDocument()

    # Attach an approval signature first (with /Contents).
    approval = _attach_signature(doc, [0, 100, 200, 50])
    approval.get_cos_object().set_item(
        COSName.get_pdf_name("Contents"), COSName.get_pdf_name("placeholder")
    )

    new_sig = PDSignature()
    with pytest.raises(ValueError, match="approval signature exists"):
        set_mdp_permission(doc, new_sig, 2)


def test_set_mdp_permission_skips_doc_time_stamp_signatures():
    """A timestamp-only signature must not block a DocMDP install."""
    doc = PDDocument()
    timestamp = _attach_signature(doc, [0, 100, 200, 50])
    ts_cos = timestamp.get_cos_object()
    ts_cos.set_item(
        COSName.get_pdf_name("Type"),
        COSName.get_pdf_name("DocTimeStamp"),
    )
    ts_cos.set_item(
        COSName.get_pdf_name("Contents"), COSName.get_pdf_name("placeholder")
    )

    cert_sig = PDSignature()
    set_mdp_permission(doc, cert_sig, 2)
    assert get_mdp_permission(doc) == 2


# ---------------------------- get_last_relevant_signature /Type filter


def test_get_last_relevant_signature_filters_unknown_type():
    """If the candidate's /Type is something other than /Sig or
    /DocTimeStamp, upstream returns None."""
    doc = PDDocument()
    sig = _attach_signature(doc, [0, 100, 200, 50])
    sig.get_cos_object().set_item(
        COSName.get_pdf_name("Type"),
        COSName.get_pdf_name("SomethingElse"),
    )
    assert get_last_relevant_signature(doc) is None


def test_get_last_relevant_signature_accepts_doc_time_stamp_type():
    doc = PDDocument()
    sig = _attach_signature(doc, [0, 100, 200, 50])
    sig.get_cos_object().set_item(
        COSName.get_pdf_name("Type"),
        COSName.get_pdf_name("DocTimeStamp"),
    )
    chosen = get_last_relevant_signature(doc)
    assert chosen is not None
    assert chosen.get_cos_object() is sig.get_cos_object()


def test_get_last_relevant_signature_accepts_explicit_sig_type():
    doc = PDDocument()
    sig = _attach_signature(doc, [0, 100, 200, 50])
    sig.get_cos_object().set_item(
        COSName.get_pdf_name("Type"),
        COSName.get_pdf_name("Sig"),
    )
    chosen = get_last_relevant_signature(doc)
    assert chosen is not None
    assert chosen.get_cos_object() is sig.get_cos_object()

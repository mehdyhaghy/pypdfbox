"""Wave 1380 — close PDSeedValue / PDSignatureLock signing-path gap.

Covers:

* :class:`PDSeedValue` typed surface — every sub-field round-trips through
  the COS dictionary.
* :class:`PDSignatureLock` typed surface — every sub-field round-trips.
* :meth:`PDSeedValue.check_signature_constraint` /
  :meth:`PDSeedValue.validate_signature` — every flagged ``/Ff`` bit is
  honoured.
* End-to-end signing — :class:`PDDocument.add_signature` +
  :meth:`PDDocument.save_incremental` with a ``cryptography``-built
  self-signed cert, reload + verify the PKCS#7 blob against the same cert.
* :meth:`PDDocument.add_signature` honours
  ``enforce_seed_value=True``: a ``/SubFilter`` mismatch against a flagged
  ``/SV`` raises before any state mutation.
* :class:`TimestampedPkcs7Signature` and :class:`DocumentTimestampSigner`
  drive the wired :class:`TSAClient` and surface tokens correctly.
"""

from __future__ import annotations

import datetime
import io
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.examples.signature.tsa_client import TSAClient
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature import (
    DocumentTimestampSigner,
    PDSeedValue,
    PDSeedValueCertificate,
    PDSeedValueMDP,
    PDSeedValueTimeStamp,
    PDSignature,
    PDSignatureLock,
    Pkcs7Signature,
    TimestampedPkcs7Signature,
)

# ---------- shared helpers ----------


def _make_self_signed_cert() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox wave 1380"),
        ]
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _build_tiny_pdf(path: Path) -> Path:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(path)
    finally:
        doc.close()
    return path


# ---------- PDSeedValue typed surface ----------


def test_pdseedvalue_filter_round_trip() -> None:
    sv = PDSeedValue()
    sv.set_filter("Adobe.PPKLite")
    assert sv.get_filter() == "Adobe.PPKLite"
    sv.set_filter(None)
    assert sv.get_filter() is None
    assert not sv.has_filter()


def test_pdseedvalue_sub_filter_round_trip() -> None:
    sv = PDSeedValue()
    sv.set_sub_filter(["adbe.pkcs7.detached", "ETSI.CAdES.detached"])
    assert sv.get_sub_filter() == ["adbe.pkcs7.detached", "ETSI.CAdES.detached"]
    sv.set_sub_filter(None)
    assert sv.get_sub_filter() is None


def test_pdseedvalue_v_round_trip() -> None:
    sv = PDSeedValue()
    # /V is stored as a COSFloat → float32 precision; use a value that
    # round-trips exactly (1.5 is exact in IEEE-754).
    sv.set_v(1.5)
    assert sv.get_v() == 1.5
    sv.set_v(None)
    assert sv.get_v() is None


def test_pdseedvalue_reasons_round_trip() -> None:
    sv = PDSeedValue()
    sv.set_reasons(["I agree", "I authored"])
    assert sv.get_reasons() == ["I agree", "I authored"]
    sv.set_reasons(None)
    assert sv.get_reasons() is None


def test_pdseedvalue_digest_method_round_trip() -> None:
    sv = PDSeedValue()
    sv.set_digest_method(["SHA256", "SHA512"])
    assert sv.get_digest_method() == ["SHA256", "SHA512"]
    with pytest.raises(ValueError, match="isn't allowed"):
        sv.set_digest_method(["NOT_REAL"])


def test_pdseedvalue_legal_attestation_round_trip() -> None:
    sv = PDSeedValue()
    sv.set_legal_attestation(["statement-A", "statement-B"])
    assert sv.get_legal_attestation() == ["statement-A", "statement-B"]


def test_pdseedvalue_mdp_round_trip() -> None:
    sv = PDSeedValue()
    mdp = PDSeedValueMDP()
    mdp.set_p(2)
    sv.set_mdp(mdp)
    fetched = sv.get_mdp()
    assert fetched is not None
    assert fetched.get_p() == 2


def test_pdseedvalue_time_stamp_round_trip() -> None:
    sv = PDSeedValue()
    ts = PDSeedValueTimeStamp()
    ts.set_url("http://tsa.example/")
    ts.set_url_required(True)
    sv.set_time_stamp(ts)
    fetched = sv.get_time_stamp()
    assert fetched is not None
    assert fetched.get_url() == "http://tsa.example/"
    assert fetched.is_url_required()


def test_pdseedvalue_certificate_round_trip() -> None:
    sv = PDSeedValue()
    cert = PDSeedValueCertificate()
    cert.set_url("http://crl.example/cert")
    sv.set_seed_value_certificate(cert)
    fetched = sv.get_seed_value_certificate()
    assert fetched is not None
    assert fetched.get_url() == "http://crl.example/cert"
    # alias surface
    assert sv.get_certificate() is not None


def test_pdseedvalue_ff_flag_bits() -> None:
    sv = PDSeedValue()
    sv.set_filter_required(True)
    sv.set_sub_filter_required(True)
    sv.set_reason_required(True)
    sv.set_digest_method_required(True)
    sv.set_add_rev_info_required(True)
    sv.set_legal_attestation_required(True)
    sv.set_v_required(True)
    assert sv.is_filter_required()
    assert sv.is_sub_filter_required()
    assert sv.is_reason_required()
    assert sv.is_digest_method_required()
    assert sv.is_add_rev_info_required()
    assert sv.is_legal_attestation_required()
    assert sv.is_v_required()
    # Toggle one off; rest must remain.
    sv.set_filter_required(False)
    assert not sv.is_filter_required()
    assert sv.is_sub_filter_required()


# ---------- PDSignatureLock typed surface ----------


def test_pdsignaturelock_action_round_trip() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_ALL)
    assert lock.get_action() == "All"
    assert lock.is_lock_all()
    lock.set_action(PDSignatureLock.ACTION_INCLUDE)
    assert lock.is_lock_include()
    lock.set_action(PDSignatureLock.ACTION_EXCLUDE)
    assert lock.is_lock_exclude()


def test_pdsignaturelock_fields_round_trip() -> None:
    lock = PDSignatureLock()
    lock.set_fields(["Name", "Address"])
    assert lock.get_fields() == ["Name", "Address"]


def test_pdsignaturelock_p_round_trip() -> None:
    lock = PDSignatureLock()
    lock.set_p(PDSignatureLock.P_NO_CHANGES)
    assert lock.get_p() == 1
    assert lock.is_no_changes()
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL)
    assert lock.is_allow_form_fill()
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL_AND_ANNOTATIONS)
    assert lock.is_allow_form_fill_and_annotations()


def test_pdsignaturelock_string_form() -> None:
    lock = PDSignatureLock()
    lock.set_action("All")
    lock.set_p(1)
    text = str(lock)
    assert "action=All" in text
    assert "p=1" in text
    assert "no_changes" in text


# ---------- PDSeedValue constraint checks ----------


def test_pdseedvalue_violation_filter() -> None:
    sv = PDSeedValue()
    sv.set_filter("Custom.Filter")
    sv.set_filter_required(True)
    sig = PDSignature()
    sig.set_filter("Adobe.PPKLite")
    violations = sv.check_signature_constraint(sig)
    assert any("Filter" in v for v in violations)
    with pytest.raises(ValueError, match="Filter"):
        sv.validate_signature(sig)


def test_pdseedvalue_violation_subfilter_passes_when_allowed() -> None:
    sv = PDSeedValue()
    sv.set_sub_filter(["adbe.pkcs7.detached", "ETSI.CAdES.detached"])
    sv.set_sub_filter_required(True)
    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    assert sv.check_signature_constraint(sig) == []


def test_pdseedvalue_violation_subfilter_rejects_unlisted() -> None:
    sv = PDSeedValue()
    sv.set_sub_filter(["ETSI.CAdES.detached"])
    sv.set_sub_filter_required(True)
    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    with pytest.raises(ValueError, match="SubFilter"):
        sv.validate_signature(sig)


def test_pdseedvalue_violation_reason() -> None:
    sv = PDSeedValue()
    sv.set_reasons(["I agree"])
    sv.set_reason_required(True)
    sig = PDSignature()
    sig.set_reason("something else")
    with pytest.raises(ValueError, match="Reason"):
        sv.validate_signature(sig)


def test_pdseedvalue_unflagged_constraints_skip_validation() -> None:
    """Constraints whose /Ff bit is not set are advisory — a wrong value
    must NOT raise. PDF 32000-1 §12.7.4.5 ``required`` semantics."""
    sv = PDSeedValue()
    sv.set_filter("Custom.Filter")
    # Note: NOT setting set_filter_required(True).
    sig = PDSignature()
    sig.set_filter("Adobe.PPKLite")
    sv.validate_signature(sig)  # must not raise


def test_pdseedvalue_validate_rejects_non_pdsignature() -> None:
    sv = PDSeedValue()
    with pytest.raises(ValueError, match="PDSignature"):
        sv.validate_signature("not a signature")


def test_pdseedvalue_legal_attestation_required() -> None:
    sv = PDSeedValue()
    sv.set_legal_attestation(["statement-A"])
    sv.set_legal_attestation_required(True)
    sig = PDSignature()
    with pytest.raises(ValueError, match="LegalAttestation"):
        sv.validate_signature(sig)


def test_pdseedvalue_add_rev_info_required() -> None:
    sv = PDSeedValue()
    sv.set_add_rev_info_required(True)
    sig = PDSignature()
    with pytest.raises(ValueError, match="AddRevInfo"):
        sv.validate_signature(sig)


# ---------- end-to-end signing + reload + verify ----------


def test_end_to_end_sign_and_verify(tmp_path: Path) -> None:
    cert, key = _make_self_signed_cert()
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out = tmp_path / "signed.pdf"

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_name("wave 1380 signer")
        sig.set_reason("end-to-end test")
        signer = Pkcs7Signature(cert, key)
        doc.add_signature(sig, signer)
        doc.save_incremental(out)

    data = out.read_bytes()
    assert data.startswith(b"%PDF-")

    # Reload + verify: /Contents must contain valid PKCS#7 SignedData
    # bound to our cert.
    with PDDocument.load(out) as reloaded:
        acro = reloaded.get_document_catalog().get_acro_form()
        assert acro is not None
        fields = acro.get_fields()
        assert len(fields) == 1
        sig_dict = (
            fields[0]
            .get_cos_object()
            .get_dictionary_object(COSName.get_pdf_name("V"))
        )
        assert isinstance(sig_dict, COSDictionary)
        loaded_sig = PDSignature(sig_dict)
        contents = loaded_sig.get_contents()
        assert contents is not None
        trimmed = contents.rstrip(b"\x00")
        certs = pkcs7.load_der_pkcs7_certificates(trimmed)
        # Cert subject must match.
        assert any(c.subject == cert.subject for c in certs)

        # ByteRange must bracket the file end-to-end.
        br = loaded_sig.get_byte_range()
        assert br is not None
        start1, len1, start2, len2 = br
        assert start1 == 0
        assert start2 + len2 == len(data)


# ---------- /SV enforcement at add_signature time ----------


def test_add_signature_enforce_seed_value_passes(tmp_path: Path) -> None:
    cert, key = _make_self_signed_cert()
    src = _build_tiny_pdf(tmp_path / "in.pdf")

    sv = PDSeedValue()
    sv.set_sub_filter(["adbe.pkcs7.detached"])
    sv.set_sub_filter_required(True)
    sv.set_filter("Adobe.PPKLite")
    sv.set_filter_required(True)

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        # Default /SubFilter populated by add_signature is
        # adbe.pkcs7.detached — must pass /SV.
        doc.add_signature(
            sig,
            Pkcs7Signature(cert, key),
            seed_value=sv,
            enforce_seed_value=True,
        )
        # If we got here, enforcement passed. No save needed for this assertion.
        assert doc.is_signature_added()


def test_add_signature_enforce_seed_value_rejects_wrong_subfilter(
    tmp_path: Path,
) -> None:
    cert, key = _make_self_signed_cert()
    src = _build_tiny_pdf(tmp_path / "in.pdf")

    sv = PDSeedValue()
    sv.set_sub_filter(["ETSI.CAdES.detached"])
    sv.set_sub_filter_required(True)

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_sub_filter("adbe.pkcs7.detached")  # disallowed
        with pytest.raises(ValueError, match="SubFilter"):
            doc.add_signature(
                sig,
                Pkcs7Signature(cert, key),
                seed_value=sv,
                enforce_seed_value=True,
            )
        # No state mutation must have happened — _signature_added stays False.
        assert not doc.is_signature_added()


def test_add_signature_enforce_seed_value_requires_seed_value() -> None:
    doc = PDDocument()
    try:
        sig = PDSignature()
        with pytest.raises(ValueError, match="requires a seed_value"):
            doc.add_signature(sig, enforce_seed_value=True)
    finally:
        doc.close()


def test_add_signature_enforce_seed_value_type_check() -> None:
    doc = PDDocument()
    try:
        sig = PDSignature()
        with pytest.raises(TypeError, match="PDSeedValue"):
            doc.add_signature(
                sig,
                seed_value="not a seed value",
                enforce_seed_value=True,
            )
    finally:
        doc.close()


# ---------- TimestampedPkcs7Signature ----------


def _fake_tsa_transport_factory(token: bytes):
    def _transport(request: bytes, url: str, headers: dict[str, str]) -> bytes:
        assert request  # the TSA must receive some bytes
        assert url == "http://tsa.example/"
        assert headers.get("Content-Type") == "application/timestamp-query"
        return token
    return _transport


def test_timestamped_signature_invokes_tsa() -> None:
    import hashlib

    cert, key = _make_self_signed_cert()
    signer = Pkcs7Signature(cert, key)
    fake_token = b"FAKE-TSP-TOKEN-DER-PAYLOAD"
    tsa = TSAClient(
        url="http://tsa.example/",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=_fake_tsa_transport_factory(fake_token),
    )

    # embed_timestamp=False keeps the wave-1380 semantics: the TSA token
    # is exposed only via last_time_stamp_token, the PKCS#7 blob is
    # untouched. Wave 1382 added the embedding default (covered by
    # test_cms_helpers_wave1382.py with a real DER-shaped token).
    ts_signer = TimestampedPkcs7Signature(signer, tsa, embed_timestamp=False)
    pkcs7_bytes = ts_signer.sign(io.BytesIO(b"document bytes to sign"))

    # The PKCS#7 blob is a real, DER-decodable SignedData.
    certs = pkcs7.load_der_pkcs7_certificates(pkcs7_bytes)
    assert any(c.subject == cert.subject for c in certs)

    # The timestamp token is exposed.
    assert ts_signer.last_time_stamp_token == fake_token


def test_timestamped_signature_rejects_non_pkcs7_signer() -> None:
    import hashlib

    tsa = TSAClient(
        url="http://tsa.example/",
        username=None,
        password=None,
        digest=hashlib.sha256(),
    )
    with pytest.raises(TypeError, match="Pkcs7Signature"):
        TimestampedPkcs7Signature("not a signer", tsa)  # type: ignore[arg-type]


# ---------- DocumentTimestampSigner ----------


def test_document_timestamp_signer_returns_tsa_token() -> None:
    import hashlib

    fake_token = b"FAKE-DOC-TIMESTAMP-TOKEN-DER"
    tsa = TSAClient(
        url="http://tsa.example/",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=_fake_tsa_transport_factory(fake_token),
    )

    dts = DocumentTimestampSigner(tsa)
    out = dts.sign(io.BytesIO(b"document bytes to timestamp"))
    assert out == fake_token


def test_document_timestamp_signer_used_with_save_incremental(
    tmp_path: Path,
) -> None:
    """End-to-end: drive a /Type /DocTimeStamp /SubFilter ETSI.RFC3161
    signature through the full save_incremental pipeline using a fake
    TSA. Reload + assert the dict carries our token in /Contents."""
    import hashlib

    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out = tmp_path / "timestamped.pdf"

    fake_token = b"\x30\x82\x01\xfe" + b"\xab" * 510  # fake DER
    tsa = TSAClient(
        url="http://tsa.example/",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=_fake_tsa_transport_factory(fake_token),
    )

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_type("DocTimeStamp")
        sig.set_sub_filter("ETSI.RFC3161")
        doc.add_signature(sig, DocumentTimestampSigner(tsa))
        doc.save_incremental(out)

    with PDDocument.load(out) as reloaded:
        acro = reloaded.get_document_catalog().get_acro_form()
        assert acro is not None
        fields = acro.get_fields()
        assert len(fields) == 1
        sig_dict = (
            fields[0]
            .get_cos_object()
            .get_dictionary_object(COSName.get_pdf_name("V"))
        )
        assert isinstance(sig_dict, COSDictionary)
        loaded = PDSignature(sig_dict)
        assert loaded.is_doc_time_stamp()
        contents = loaded.get_contents()
        assert contents is not None
        # /Contents must start with our fake token bytes (trailing zeros
        # are the placeholder padding the splice didn't fill).
        assert contents.startswith(fake_token)

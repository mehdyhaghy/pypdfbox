"""Tests for ``SigUtils``."""

from __future__ import annotations

import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import (
    ExtendedKeyUsageOID,
    NameOID,
)

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.examples.signature.sig_utils import SigUtils
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.pd_document import PDDocument

# ---------------------------------------------------------------------------
# Register the static COSName constants referenced by SigUtils. The cos_name
# module's predefined catalogue is intentionally minimal (see
# ``pypdfbox/cos/cos_name.py``); the signature package referenced names live
# only as dynamically interned values. Setting them once as class attributes
# lets the helpers run without monkeypatching every call site.
# ---------------------------------------------------------------------------
_SIG_UTILS_NAMES = {
    "PERMS": "Perms",
    "DOCMDP": "DocMDP",
    "REFERENCE": "Reference",
    "TRANSFORM_METHOD": "TransformMethod",
    "TRANSFORM_PARAMS": "TransformParams",
    "SIG_REF": "SigRef",
    "DIGEST_METHOD": "DigestMethod",
    "DOC_TIME_STAMP": "DocTimeStamp",
    "SIG": "Sig",
    "P": "P",
    "V": "V",
}
for _attr, _pdf in _SIG_UTILS_NAMES.items():
    if not hasattr(COSName, _attr):
        setattr(COSName, _attr, COSName.get_pdf_name(_pdf))


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _build_cert(
    *,
    extended_key_usage: list | None = None,
    digital_signature: bool = True,
    content_commitment: bool = True,
    include_key_usage: bool = True,
) -> x509.Certificate:
    """Build an in-memory self-signed certificate with explicit KU / EKU."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
    )
    if include_key_usage:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=digital_signature,
                content_commitment=content_commitment,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    if extended_key_usage is not None:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage(extended_key_usage),
            critical=False,
        )
    return builder.sign(key, hashes.SHA256())


# ---------------------------------------------------------------------------
# Static-helper boilerplate
# ---------------------------------------------------------------------------


def test_static_helper_cannot_be_instantiated():
    with pytest.raises(RuntimeError):
        SigUtils()


# ---------------------------------------------------------------------------
# check_certificate_usage
# ---------------------------------------------------------------------------


def test_check_certificate_usage_accepts_signing_cert(self_signed_cert, caplog):
    cert, _ = self_signed_cert
    caplog.clear()
    SigUtils.check_certificate_usage(cert)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


def test_check_certificate_usage_logs_when_ku_lacks_signature(caplog):
    cert = _build_cert(
        digital_signature=False,
        content_commitment=False,
        extended_key_usage=[ExtendedKeyUsageOID.CODE_SIGNING],
    )
    with caplog.at_level("ERROR"):
        SigUtils.check_certificate_usage(cert)
    assert any("digitalSignature" in r.message for r in caplog.records)


def test_check_certificate_usage_silent_without_key_usage(caplog):
    cert = _build_cert(
        include_key_usage=False,
        extended_key_usage=[ExtendedKeyUsageOID.CODE_SIGNING],
    )
    caplog.clear()
    SigUtils.check_certificate_usage(cert)
    # No KU extension → ExtensionNotFound swallowed; EKU is acceptable.
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


def test_check_certificate_usage_logs_when_eku_unacceptable(caplog):
    cert = _build_cert(
        extended_key_usage=[ExtendedKeyUsageOID.SERVER_AUTH],
    )
    with caplog.at_level("ERROR"):
        SigUtils.check_certificate_usage(cert)
    assert any("extended key usage" in r.message for r in caplog.records)


def test_check_certificate_usage_accepts_any_eku(caplog):
    cert = _build_cert(
        extended_key_usage=[ExtendedKeyUsageOID.ANY_EXTENDED_KEY_USAGE],
    )
    caplog.clear()
    SigUtils.check_certificate_usage(cert)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


def test_check_certificate_usage_accepts_adobe_authentic_oid(caplog):
    cert = _build_cert(
        extended_key_usage=[x509.ObjectIdentifier("1.2.840.113583.1.1.5")],
    )
    caplog.clear()
    SigUtils.check_certificate_usage(cert)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


def test_check_certificate_usage_accepts_ms_doc_signing_oid(caplog):
    cert = _build_cert(
        extended_key_usage=[x509.ObjectIdentifier("1.3.6.1.4.1.311.10.3.12")],
    )
    caplog.clear()
    SigUtils.check_certificate_usage(cert)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


# ---------------------------------------------------------------------------
# check_time_stamp_certificate_usage / check_responder_certificate_usage
# ---------------------------------------------------------------------------


def test_check_time_stamp_usage_logs_for_non_timestamp_cert(self_signed_cert, caplog):
    cert, _ = self_signed_cert
    with caplog.at_level("ERROR"):
        SigUtils.check_time_stamp_certificate_usage(cert)
    assert any("timeStamping" in r.message for r in caplog.records)


def test_check_time_stamp_usage_silent_for_tsa_cert(caplog):
    cert = _build_cert(extended_key_usage=[ExtendedKeyUsageOID.TIME_STAMPING])
    caplog.clear()
    SigUtils.check_time_stamp_certificate_usage(cert)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


def test_check_time_stamp_usage_silent_without_eku(caplog):
    cert = _build_cert(extended_key_usage=None)
    caplog.clear()
    SigUtils.check_time_stamp_certificate_usage(cert)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


def test_check_responder_usage_logs_for_non_ocsp_cert(self_signed_cert, caplog):
    cert, _ = self_signed_cert
    with caplog.at_level("ERROR"):
        SigUtils.check_responder_certificate_usage(cert)
    assert any("OCSP" in r.message for r in caplog.records)


def test_check_responder_usage_silent_for_ocsp_cert(caplog):
    cert = _build_cert(extended_key_usage=[ExtendedKeyUsageOID.OCSP_SIGNING])
    caplog.clear()
    SigUtils.check_responder_certificate_usage(cert)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


# ---------------------------------------------------------------------------
# _extended_key_usage helper (indirectly via above; once directly)
# ---------------------------------------------------------------------------


def test_extended_key_usage_returns_none_when_absent():
    cert = _build_cert(extended_key_usage=None)
    assert SigUtils._extended_key_usage(cert) is None


def test_extended_key_usage_returns_dotted_oids():
    cert = _build_cert(extended_key_usage=[ExtendedKeyUsageOID.CODE_SIGNING])
    oids = SigUtils._extended_key_usage(cert)
    assert oids == [ExtendedKeyUsageOID.CODE_SIGNING.dotted_string]


# ---------------------------------------------------------------------------
# get_mdp_permission
# ---------------------------------------------------------------------------


def test_get_mdp_permission_returns_zero_without_perms():
    doc = PDDocument()
    try:
        assert SigUtils.get_mdp_permission(doc) == 0
    finally:
        doc.close()


def test_get_mdp_permission_returns_zero_without_docmdp():
    doc = PDDocument()
    try:
        catalog = doc.get_document_catalog().get_cos_object()
        catalog.set_item(COSName.PERMS, COSDictionary())
        assert SigUtils.get_mdp_permission(doc) == 0
    finally:
        doc.close()


def test_get_mdp_permission_returns_zero_without_reference_array():
    doc = PDDocument()
    try:
        catalog = doc.get_document_catalog().get_cos_object()
        perms = COSDictionary()
        perms.set_item(COSName.DOCMDP, COSDictionary())
        catalog.set_item(COSName.PERMS, perms)
        assert SigUtils.get_mdp_permission(doc) == 0
    finally:
        doc.close()


def test_get_mdp_permission_extracts_p_value():
    doc = PDDocument()
    try:
        catalog = doc.get_document_catalog().get_cos_object()
        perms = COSDictionary()
        docmdp_sig = COSDictionary()
        ref = COSDictionary()
        ref.set_item(COSName.TRANSFORM_METHOD, COSName.DOCMDP)
        params = COSDictionary()
        params.set_int(COSName.P, 2)
        ref.set_item(COSName.TRANSFORM_PARAMS, params)
        ref_array = COSArray()
        ref_array.add(ref)
        docmdp_sig.set_item(COSName.REFERENCE, ref_array)
        perms.set_item(COSName.DOCMDP, docmdp_sig)
        catalog.set_item(COSName.PERMS, perms)

        assert SigUtils.get_mdp_permission(doc) == 2
    finally:
        doc.close()


def test_get_mdp_permission_clamps_out_of_range_p():
    doc = PDDocument()
    try:
        catalog = doc.get_document_catalog().get_cos_object()
        perms = COSDictionary()
        docmdp_sig = COSDictionary()
        ref = COSDictionary()
        ref.set_item(COSName.TRANSFORM_METHOD, COSName.DOCMDP)
        params = COSDictionary()
        params.set_int(COSName.P, 99)
        ref.set_item(COSName.TRANSFORM_PARAMS, params)
        ref_array = COSArray()
        ref_array.add(ref)
        docmdp_sig.set_item(COSName.REFERENCE, ref_array)
        perms.set_item(COSName.DOCMDP, docmdp_sig)
        catalog.set_item(COSName.PERMS, perms)

        assert SigUtils.get_mdp_permission(doc) == 2
    finally:
        doc.close()


def test_get_mdp_permission_returns_zero_for_non_docmdp_transform():
    doc = PDDocument()
    try:
        catalog = doc.get_document_catalog().get_cos_object()
        perms = COSDictionary()
        docmdp_sig = COSDictionary()
        ref = COSDictionary()
        # Different transform method -> ignored.
        ref.set_item(COSName.TRANSFORM_METHOD, COSName.get_pdf_name("FieldMDP"))
        ref_array = COSArray()
        ref_array.add(ref)
        docmdp_sig.set_item(COSName.REFERENCE, ref_array)
        perms.set_item(COSName.DOCMDP, docmdp_sig)
        catalog.set_item(COSName.PERMS, perms)

        assert SigUtils.get_mdp_permission(doc) == 0
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# set_mdp_permission
# ---------------------------------------------------------------------------


def test_set_mdp_permission_writes_perms_and_reference():
    doc = PDDocument()
    try:
        # wave 1486: add_signature refuses a page-less document (upstream
        # IllegalStateException) — give the fixture a page.
        doc.add_page(PDPage())
        signature = PDSignature()
        doc.add_signature(signature)

        SigUtils.set_mdp_permission(doc, signature, 1)

        catalog = doc.get_document_catalog().get_cos_object()
        perms = catalog.get_cos_dictionary(COSName.PERMS)
        assert perms is not None
        assert perms.get_dictionary_object(COSName.DOCMDP) is signature
        ref_array = signature.get_cos_object().get_cos_array(COSName.REFERENCE)
        assert ref_array is not None and ref_array.size() == 1
        ref = ref_array.get_object(0)
        assert ref.get_dictionary_object(COSName.TRANSFORM_METHOD) == COSName.DOCMDP
        params = ref.get_dictionary_object(COSName.TRANSFORM_PARAMS)
        assert params.get_int(COSName.P) == 1
    finally:
        doc.close()


def test_set_mdp_permission_reuses_existing_perms_dict():
    doc = PDDocument()
    try:
        # wave 1486: add_signature refuses a page-less document (upstream
        # IllegalStateException) — give the fixture a page.
        doc.add_page(PDPage())
        signature = PDSignature()
        doc.add_signature(signature)

        catalog = doc.get_document_catalog().get_cos_object()
        seed = COSDictionary()
        seed.set_item(COSName.get_pdf_name("UR3"), COSDictionary())
        catalog.set_item(COSName.PERMS, seed)

        SigUtils.set_mdp_permission(doc, signature, 3)

        perms = catalog.get_cos_dictionary(COSName.PERMS)
        assert perms is seed
        assert perms.get_dictionary_object(COSName.get_pdf_name("UR3")) is not None
        assert perms.get_dictionary_object(COSName.DOCMDP) is signature
    finally:
        doc.close()


def test_set_mdp_permission_rejects_when_approval_signature_present():
    doc = PDDocument()
    try:
        # wave 1486: add_signature refuses a page-less document (upstream
        # IllegalStateException) — give the fixture a page.
        doc.add_page(PDPage())
        existing = PDSignature()
        existing.get_cos_object().set_string(COSName.CONTENTS, "X")
        doc.add_signature(existing)
        new_sig = PDSignature()

        with pytest.raises(OSError, match="DocMDP"):
            SigUtils.set_mdp_permission(doc, new_sig, 1)
    finally:
        doc.close()


def test_set_mdp_permission_skips_doctimestamp_when_scanning():
    doc = PDDocument()
    try:
        # wave 1486: add_signature refuses a page-less document (upstream
        # IllegalStateException) — give the fixture a page.
        doc.add_page(PDPage())
        tsa_sig = PDSignature()
        tsa_sig.get_cos_object().set_item(COSName.TYPE, COSName.DOC_TIME_STAMP)
        tsa_sig.get_cos_object().set_string(COSName.CONTENTS, "X")
        doc.add_signature(tsa_sig)

        SigUtils.set_mdp_permission(doc, tsa_sig, 2)

        catalog = doc.get_document_catalog().get_cos_object()
        perms = catalog.get_cos_dictionary(COSName.PERMS)
        assert perms.get_dictionary_object(COSName.DOCMDP) is tsa_sig
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# get_last_relevant_signature
# ---------------------------------------------------------------------------


def test_get_last_relevant_signature_returns_none_when_empty():
    doc = PDDocument()
    try:
        assert SigUtils.get_last_relevant_signature(doc) is None
    finally:
        doc.close()


def test_get_last_relevant_signature_returns_last_sig():
    doc = PDDocument()
    try:
        # wave 1486: add_signature refuses a page-less document (upstream
        # IllegalStateException) — give the fixture a page.
        doc.add_page(PDPage())
        signature = PDSignature()
        signature.set_byte_range([0, 1, 2, 100])
        doc.add_signature(signature)
        last = SigUtils.get_last_relevant_signature(doc)
        assert last is not None
        assert last.get_cos_object() is signature.get_cos_object()
    finally:
        doc.close()


def test_get_last_relevant_signature_returns_none_for_unknown_type():
    doc = PDDocument()
    try:
        # wave 1486: add_signature refuses a page-less document (upstream
        # IllegalStateException) — give the fixture a page.
        doc.add_page(PDPage())
        signature = PDSignature()
        signature.set_byte_range([0, 1, 2, 100])
        # Override /Type with a non-signature value.
        signature.get_cos_object().set_item(
            COSName.TYPE, COSName.get_pdf_name("FieldMDP")
        )
        doc.add_signature(signature)
        assert SigUtils.get_last_relevant_signature(doc) is None
    finally:
        doc.close()


def test_get_last_relevant_signature_accepts_doctimestamp():
    doc = PDDocument()
    try:
        # wave 1486: add_signature refuses a page-less document (upstream
        # IllegalStateException) — give the fixture a page.
        doc.add_page(PDPage())
        signature = PDSignature()
        signature.set_byte_range([0, 1, 2, 100])
        signature.get_cos_object().set_item(COSName.TYPE, COSName.DOC_TIME_STAMP)
        doc.add_signature(signature)
        last = SigUtils.get_last_relevant_signature(doc)
        assert last is not None
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Trivial stubs (kept for parity with upstream surface)
# ---------------------------------------------------------------------------


def test_extract_time_stamp_token_returns_none():
    assert SigUtils.extract_time_stamp_token_from_signer_information(object()) is None


def test_validate_timestamp_token_is_noop():
    # No return, no raise.
    assert SigUtils.validate_timestamp_token(object()) is None


def test_get_tsa_certificate_returns_none():
    assert SigUtils.get_tsa_certificate("http://tsa.test.invalid") is None


def test_get_certificate_from_time_stamp_token_returns_none():
    assert SigUtils.get_certificate_from_time_stamp_token(object()) is None


def test_open_url_returns_empty_bytes():
    assert SigUtils.open_url("http://example.invalid") == b""


def test_verify_certificate_chain_delegates_to_verifier(self_signed_cert):
    cert, _ = self_signed_cert
    # CertificateVerifier.verify_certificate accepts a self-signed cert and
    # returns without raising when verify_self_signed_cert=True.
    SigUtils.verify_certificate_chain([], cert, sign_date=None)


# ---------------------------------------------------------------------------
# check_cross_reference_table
# ---------------------------------------------------------------------------


def test_check_cross_reference_table_silent_for_empty():
    doc = PDDocument()
    try:
        # Fresh doc: xref table may be empty -> no warnings emitted.
        SigUtils.check_cross_reference_table(doc)
    finally:
        doc.close()


def test_check_cross_reference_table_warns_on_gap(caplog):
    doc = PDDocument()
    try:
        xref = doc.get_document().get_xref_table()
        xref[COSObjectKey(1)] = 10
        xref[COSObjectKey(3)] = 20  # gap at 2
        xref[COSObjectKey(5)] = 30  # gap at 4
        with caplog.at_level("WARNING"):
            SigUtils.check_cross_reference_table(doc)
        warns = [r for r in caplog.records if r.levelname == "WARNING"]
        missing = {r.args[0] for r in warns}
        assert 2 in missing and 4 in missing
    finally:
        doc.close()


def test_check_cross_reference_table_silent_for_contiguous():
    doc = PDDocument()
    try:
        xref = doc.get_document().get_xref_table()
        # 1..n contiguous -> len(keys) == n, no gap branch.
        for n in (1, 2, 3):
            xref[COSObjectKey(n)] = n * 10
        # Should be silent (no warnings).
        SigUtils.check_cross_reference_table(doc)
    finally:
        doc.close()


def test_check_cross_reference_table_handles_missing_xref_attr():
    class Stub:
        def get_document(self):
            return object()  # no get_xref_table → AttributeError swallowed

    # Should not raise.
    SigUtils.check_cross_reference_table(Stub())  # type: ignore[arg-type]

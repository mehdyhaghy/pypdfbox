"""Tests for ``OcspHelper``."""

import datetime as _dt
import hashlib

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import ocsp
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.cert.ocsp_helper import OcspException, OcspHelper
from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _build_cert_with_key() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ocsp-test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _build_response(
    cert: x509.Certificate,
    issuer: x509.Certificate,
    issuer_key: rsa.RSAPrivateKey,
    *,
    cert_status: ocsp.OCSPCertStatus = ocsp.OCSPCertStatus.GOOD,
    revocation_time: _dt.datetime | None = None,
    revocation_reason: x509.ReasonFlags | None = None,
) -> ocsp.OCSPResponse:
    builder = ocsp.OCSPResponseBuilder()
    builder = builder.add_response(
        cert=cert,
        issuer=issuer,
        algorithm=hashes.SHA1(),
        cert_status=cert_status,
        this_update=_dt.datetime.now(_dt.UTC),
        next_update=_dt.datetime.now(_dt.UTC) + _dt.timedelta(hours=1),
        revocation_time=revocation_time,
        revocation_reason=revocation_reason,
    ).responder_id(ocsp.OCSPResponderEncoding.HASH, issuer)
    return builder.sign(issuer_key, hashes.SHA256())


# ---------------------------------------------------------------------------
# Construction / simple accessors
# ---------------------------------------------------------------------------


def test_constructor_stores_inputs(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    helper = OcspHelper(
        cert_to_check=cert,
        sign_date=None,
        issuer_certificate=cert,
        additional_certs=[],
        ocsp_url="http://ocsp.test.invalid/check",
    )
    assert helper.get_ocsp_url() == "http://ocsp.test.invalid/check"
    assert helper.get_ocsp_responder_certificate() is None
    assert helper.get_basic_ocsp_resp() is None
    assert helper.get_certificate_to_check() is cert
    assert helper.get_issuer_certificate() is cert
    assert helper.get_nonce() is None


def test_additional_certs_iterable_is_materialised(self_signed_cert):
    cert, _ = self_signed_cert

    def _gen():
        yield cert

    helper = OcspHelper(cert, None, cert, _gen(), "http://x")
    # Internal copy is a list (iterating twice is safe).
    assert helper._additional_certs == [cert]


def test_get_ocsp_responder_certificate_returns_none_without_response(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    assert helper.get_ocsp_responder_certificate() is None


def test_get_ocsp_responder_certificate_set_by_verification(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [cert], "http://x")
    helper.verify_ocsp_response(_build_response(cert, cert, key))
    # Responder is located by key hash in ``additional_certs``.
    assert helper.get_ocsp_responder_certificate() == cert


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------


def test_build_ocsp_request_returns_non_empty_der(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    helper = OcspHelper(cert, None, cert, [], "http://ocsp.test.invalid")
    blob = helper.build_ocsp_request()
    assert isinstance(blob, bytes)
    assert blob.startswith(b"\x30")  # SEQUENCE tag
    # Nonce captured for later check_nonce parity.
    assert helper.get_nonce() is not None
    assert len(helper.get_nonce()) == 16


def test_build_ocsp_request_parses_back(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    helper = OcspHelper(cert, None, cert, [], "http://ocsp.test.invalid")
    blob = helper.build_ocsp_request()
    parsed = ocsp.load_der_ocsp_request(blob)
    assert parsed.serial_number == cert.serial_number


def test_generate_ocsp_request_delegates_to_build(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    blob = helper.generate_ocsp_request()
    assert isinstance(blob, bytes)
    assert blob.startswith(b"\x30")


def test_create16_bytes_nonce_yields_fresh_bytes(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    first = helper.create16_bytes_nonce()
    second = helper.create16_bytes_nonce()
    assert len(first) == 16
    assert len(second) == 16
    assert first != second
    assert helper.get_nonce() == second


# ---------------------------------------------------------------------------
# Nonce check
# ---------------------------------------------------------------------------


def test_check_nonce_matches(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    helper._encoded_nonce = b"a" * 16
    helper.check_nonce(b"a" * 16)  # no raise


def test_check_nonce_silent_when_no_local_nonce(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    helper.check_nonce(b"anything")  # no local nonce → silent


def test_check_nonce_silent_when_request_nonce_none(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    helper._encoded_nonce = b"a" * 16
    helper.check_nonce(None)  # remote did not echo → silent


def test_check_nonce_mismatch_raises(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    helper._encoded_nonce = b"a" * 16
    with pytest.raises(OcspException, match="nonce mismatch"):
        helper.check_nonce(b"b" * 16)


# ---------------------------------------------------------------------------
# Trivial parity getters / no-op stubs
# ---------------------------------------------------------------------------


def test_get_ocsp_resp_status_returns_string(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    resp = _build_response(cert, cert, key)
    assert "SUCCESSFUL" in helper.get_ocsp_resp_status(resp)


def test_check_ocsp_signature_raises_when_no_response(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    with pytest.raises(OcspException, match="No OCSP response captured"):
        helper.check_ocsp_signature(object())


def test_check_ocsp_signature_valid_with_stored_response(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    helper._response_ocsp = _build_response(cert, cert, key)
    helper.check_ocsp_signature(cert)  # no raise


def test_check_responder_cert_accepts_issuer(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    assert helper.check_responder_cert(cert) is None


def test_perform_request_offline_raises_os_error(self_signed_cert):
    # The autouse conftest fixture blocks the network.
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    with pytest.raises(OSError):
        helper.perform_request("http://x")


def test_find_responder_certificate_by_key_hash_returns_none(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    resp = _build_response(cert, cert, key)
    assert helper.find_responder_certificate_by_key_hash(resp, b"hash") is None
    assert helper.get_ocsp_responder_certificate() is None


def test_find_responder_certificate_by_name_returns_none(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    resp = _build_response(cert, cert, key)
    other = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "nobody")])
    assert helper.find_responder_certificate_by_name(resp, other) is None


# ---------------------------------------------------------------------------
# Key-hash helper
# ---------------------------------------------------------------------------


def test_get_key_hash_from_cert_holder_returns_sha1(self_signed_cert):
    cert, _ = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    digest = helper.get_key_hash_from_cert_holder(cert)

    # RFC 6960 KeyHash: SHA-1 over the subjectPublicKey BIT STRING value
    # (no tag / length / unused-bits octet) — same as the RFC 5280 SKI.
    expected = x509.SubjectKeyIdentifier.from_public_key(cert.public_key()).digest
    assert digest == expected
    full_spki = hashlib.sha1(
        cert.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        usedforsecurity=False,
    ).digest()
    assert digest != full_spki
    assert len(digest) == 20


# ---------------------------------------------------------------------------
# verify_resp_status / verify_ocsp_response
# ---------------------------------------------------------------------------


def test_verify_resp_status_accepts_good(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [], "http://x")
    resp = _build_response(cert, cert, key, cert_status=ocsp.OCSPCertStatus.GOOD)
    helper.verify_resp_status(resp)  # SUCCESSFUL → no raise


def test_verify_ocsp_response_delegates_and_stores(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [cert], "http://x")
    resp = _build_response(cert, cert, key)
    helper.verify_ocsp_response(resp)
    assert helper.get_basic_ocsp_resp() is resp


def test_verify_ocsp_response_raises_for_revoked(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [cert], "http://x")
    revoked_at = _dt.datetime.now(_dt.UTC) - _dt.timedelta(hours=1)
    resp = _build_response(
        cert,
        cert,
        key,
        cert_status=ocsp.OCSPCertStatus.REVOKED,
        revocation_time=revoked_at.replace(tzinfo=None),
        revocation_reason=x509.ReasonFlags.key_compromise,
    )
    with pytest.raises(RevokedCertificateException) as ei:
        helper.verify_ocsp_response(resp)
    # Revocation time bubbles through to the exception.
    assert ei.value.get_revocation_time() is not None


def test_verify_ocsp_response_raises_for_unknown(self_signed_cert):
    cert, key = self_signed_cert
    helper = OcspHelper(cert, None, cert, [cert], "http://x")
    resp = _build_response(cert, cert, key, cert_status=ocsp.OCSPCertStatus.UNKNOWN)
    with pytest.raises(OcspException, match="Status of Cert is unknown"):
        helper.verify_ocsp_response(resp)


def test_verify_resp_status_raises_for_unsuccessful():
    # Build a non-successful response (e.g. unauthorized) via the builder.
    cert, key = _build_cert_with_key()
    helper = OcspHelper(cert, None, cert, [], "http://x")
    unauth = ocsp.OCSPResponseBuilder.build_unsuccessful(
        ocsp.OCSPResponseStatus.UNAUTHORIZED
    )
    with pytest.raises(OcspException, match="unsuccessful, status: UNAUTHORIZED"):
        helper.verify_resp_status(unauth)


# ---------------------------------------------------------------------------
# OcspException
# ---------------------------------------------------------------------------


def test_ocsp_exception_is_exception():
    with pytest.raises(OcspException):
        raise OcspException("bad")

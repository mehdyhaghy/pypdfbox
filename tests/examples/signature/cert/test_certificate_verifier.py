"""Tests for ``CertificateVerifier``."""

from __future__ import annotations

import pytest

from pypdfbox.examples.signature.cert.certificate_verifier import (
    CertificateVerificationException,
    CertificateVerifier,
)


def test_static_helper_cannot_be_instantiated():
    with pytest.raises(RuntimeError):
        CertificateVerifier()


def test_is_self_signed_true_for_self_signed_cert(self_signed_cert):
    cert, _ = self_signed_cert
    assert CertificateVerifier.is_self_signed(cert) is True


def test_verify_certificate_rejects_self_signed_when_disallowed(self_signed_cert):
    cert, _ = self_signed_cert
    result = CertificateVerifier.verify_certificate(
        cert, additional_certs=[], verify_self_signed_cert=False, sign_date=None
    )
    assert result.is_valid() is False
    assert isinstance(result.get_exception(), CertificateVerificationException)


def test_verify_certificate_accepts_self_signed_when_allowed(self_signed_cert):
    cert, _ = self_signed_cert
    result = CertificateVerifier.verify_certificate(
        cert, additional_certs=[cert], verify_self_signed_cert=True, sign_date=None
    )
    assert result.is_valid() is True
    assert result.get_result() == [cert]


def test_extract_ocsp_url(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    assert (
        CertificateVerifier.extract_ocsp_url(cert)
        == "http://ocsp.test.invalid/check"
    )


def test_extract_ca_issuers_url(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    urls = CertificateVerifier.extract_ca_issuers_url(cert)
    assert urls == ["http://ca.test.invalid/issuer.crt"]


def test_download_extra_certificates_returns_empty_set(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    # Offline-safe stub — should not attempt the network.
    assert CertificateVerifier.download_extra_certificates(cert) == set()

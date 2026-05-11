"""Tests for ``CRLVerifier``."""

from __future__ import annotations

import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from pypdfbox.examples.signature.cert.crl_verifier import CRLVerifier
from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)


def test_static_helper_cannot_be_instantiated():
    with pytest.raises(RuntimeError):
        CRLVerifier()


def test_get_crl_distribution_points_round_trip(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    urls = CRLVerifier.get_crl_distribution_points(cert)
    assert urls == ["http://crl.test.invalid/list.crl"]


def test_get_crl_distribution_points_returns_empty_when_missing(self_signed_cert):
    cert, _ = self_signed_cert
    assert CRLVerifier.get_crl_distribution_points(cert) == []


def _build_crl(issuer_cert, issuer_key, revoked_serials: list[int]):
    now = _dt.datetime.now(_dt.UTC)
    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(issuer_cert.subject)
        .last_update(now - _dt.timedelta(hours=1))
        .next_update(now + _dt.timedelta(days=1))
    )
    for serial in revoked_serials:
        revoked = (
            x509.RevokedCertificateBuilder()
            .serial_number(serial)
            .revocation_date(now - _dt.timedelta(minutes=10))
            .build()
        )
        builder = builder.add_revoked_certificate(revoked)
    return builder.sign(issuer_key, hashes.SHA256())


def test_check_revocation_raises_when_serial_is_revoked(self_signed_with_revocation):
    cert, key = self_signed_with_revocation
    crl = _build_crl(cert, key, [cert.serial_number])
    with pytest.raises(RevokedCertificateException):
        CRLVerifier.check_revocation(crl, cert, sign_date=_dt.datetime.now(_dt.UTC))


def test_check_revocation_silent_when_serial_not_listed(self_signed_with_revocation):
    cert, key = self_signed_with_revocation
    crl = _build_crl(cert, key, [])
    CRLVerifier.check_revocation(crl, cert, sign_date=_dt.datetime.now(_dt.UTC))


def test_verify_certificate_crls_uses_overrides(self_signed_with_revocation):
    cert, key = self_signed_with_revocation
    crl = _build_crl(cert, key, [cert.serial_number])
    with pytest.raises(RevokedCertificateException):
        CRLVerifier.verify_certificate_crls(
            cert,
            sign_date=_dt.datetime.now(_dt.UTC),
            additional_certs=[],
            crl_overrides={"http://crl.test.invalid/list.crl": crl},
        )

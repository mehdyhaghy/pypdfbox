"""Wave 1345 — coverage round-out for :class:`CRLVerifier`.

Targets the remaining uncovered branches:

* the ``LOG.warning`` / ``continue`` when no CRL override is provided for
  a distribution point (lines 50-51);
* the snake-case alias :meth:`verify_certificate_cr_ls` (line 62);
* the post-revocation-date short-circuit in :meth:`check_revocation`
  (line 79);
* the three offline-by-default ``download_crl*`` placeholders
  (lines 88, 93, 98);
* the ``if not full_name`` continue in
  :meth:`get_crl_distribution_points` (line 113).
"""

from __future__ import annotations

import datetime as _dt
import logging

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.cert.crl_verifier import CRLVerifier


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


def test_verify_certificate_crls_warns_when_no_override(
    self_signed_with_revocation, caplog: pytest.LogCaptureFixture,
):
    """No CRL override for a URL → LOG.warning + continue (lines 50-51)."""
    cert, _ = self_signed_with_revocation
    with caplog.at_level(logging.WARNING):
        # Empty overrides dict (default) — every distribution point falls
        # through the warning branch.
        CRLVerifier.verify_certificate_crls(
            cert,
            sign_date=_dt.datetime.now(_dt.UTC),
            additional_certs=[],
            crl_overrides=None,
        )
    assert any("No CRL provided" in record.message for record in caplog.records)


def test_verify_certificate_cr_ls_alias_delegates(
    self_signed_with_revocation,
):
    """The ``verify_certificate_cr_ls`` snake-case alias delegates to the
    canonical method (line 62)."""
    cert, key = self_signed_with_revocation
    crl = _build_crl(cert, key, [cert.serial_number])
    # Same revocation error path as the canonical method.
    from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
        RevokedCertificateException,
    )

    with pytest.raises(RevokedCertificateException):
        CRLVerifier.verify_certificate_cr_ls(
            cert,
            sign_date=_dt.datetime.now(_dt.UTC),
            additional_certs=[],
            crl_overrides={"http://crl.test.invalid/list.crl": crl},
        )


def test_check_revocation_ignores_revocations_after_sign_date(
    self_signed_with_revocation,
):
    """Revocation date *after* the signing date is silently ignored —
    line 79."""
    cert, key = self_signed_with_revocation
    crl = _build_crl(cert, key, [cert.serial_number])
    # Sign date is a year ago — well before the revocation entry we just
    # built. ``check_revocation`` must return None, not raise.
    sign_date = _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=365)
    # No raise expected.
    CRLVerifier.check_revocation(crl, cert, sign_date=sign_date)


def test_download_crl_returns_empty_bytes() -> None:
    """Offline HTTP placeholder returns ``b''`` (line 88)."""
    assert CRLVerifier.download_crl("http://example.test/list.crl") == b""


def test_download_crl_from_web_returns_empty_bytes() -> None:
    """Offline HTTPS placeholder returns ``b''`` (line 93)."""
    assert CRLVerifier.download_crl_from_web("https://example.test/list.crl") == b""


def test_download_crl_from_ldap_returns_empty_bytes() -> None:
    """Offline LDAP placeholder returns ``b''`` (line 98)."""
    assert (
        CRLVerifier.download_crl_from_ldap("ldap://example.test/cn=crl") == b""
    )


def _self_signed_crl_dp_without_full_name() -> x509.Certificate:
    """Self-signed cert whose CRL distribution point omits ``full_name``
    (covered by a ``relative_name`` instead). The walker's ``if not
    full_name`` branch (line 113) takes the ``continue``.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-empty-fullname")]
    )
    relative_name = x509.RelativeDistinguishedName(
        [x509.NameAttribute(NameOID.COMMON_NAME, "crl-rdn")]
    )
    crl_dp = x509.DistributionPoint(
        full_name=None,
        relative_name=relative_name,
        reasons=None,
        crl_issuer=None,
    )
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .add_extension(
            x509.CRLDistributionPoints([crl_dp]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )


def test_get_crl_distribution_points_skips_dp_without_full_name() -> None:
    """A CRL DP that lacks ``full_name`` falls through the ``if not
    full_name`` continue (line 113), yielding no URLs."""
    cert = _self_signed_crl_dp_without_full_name()
    assert CRLVerifier.get_crl_distribution_points(cert) == []

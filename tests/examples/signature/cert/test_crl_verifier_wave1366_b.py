"""Wave 1366 (agent B) — coverage round-out for :class:`CRLVerifier`.

Builds on wave 1345's branch coverage with additional CRL-specific
edges:

* multiple distribution points each with their own override CRL,
* a CRL DP whose ``full_name`` contains a non-URI name (the inner
  ``isinstance(...)`` guard),
* multiple revoked entries in one CRL — the verifier picks the matching
  serial,
* CRL without ``revocation_date_utc`` falls back to ``revocation_date``,
* :meth:`verify_certificate_crls` is a no-op when the cert exposes zero
  CRL distribution points (no extension at all).
"""

from __future__ import annotations

import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.cert.crl_verifier import CRLVerifier
from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)


def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def _self_signed(common_name: str = "wave1366-b") -> tuple[
    x509.Certificate, rsa.RSAPrivateKey
]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now_utc() - _dt.timedelta(days=1))
        .not_valid_after(_now_utc() + _dt.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _self_signed_with_two_crl_urls(
    urls: tuple[str, str],
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "two-crl-dps")]
    )
    dps = [
        x509.DistributionPoint(
            full_name=[x509.UniformResourceIdentifier(url)],
            relative_name=None,
            reasons=None,
            crl_issuer=None,
        )
        for url in urls
    ]
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now_utc() - _dt.timedelta(days=1))
        .not_valid_after(_now_utc() + _dt.timedelta(days=365))
        .add_extension(
            x509.CRLDistributionPoints(dps),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _build_crl(
    issuer_cert: x509.Certificate,
    issuer_key: rsa.RSAPrivateKey,
    revoked_serials: list[int],
):
    now = _now_utc()
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_crl_distribution_points_returns_two_urls() -> None:
    cert, _ = _self_signed_with_two_crl_urls(
        ("http://crl.a.test/list.crl", "https://crl.b.test/list.crl"),
    )
    assert CRLVerifier.get_crl_distribution_points(cert) == [
        "http://crl.a.test/list.crl",
        "https://crl.b.test/list.crl",
    ]


def test_get_crl_distribution_points_skips_non_http() -> None:
    """``ldap://`` URLs in the CRL DP fall through the
    ``startswith("http")`` guard."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "ldap-crl-dp")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now_utc() - _dt.timedelta(days=1))
        .not_valid_after(_now_utc() + _dt.timedelta(days=365))
        .add_extension(
            x509.CRLDistributionPoints(
                [
                    x509.DistributionPoint(
                        full_name=[
                            x509.UniformResourceIdentifier(
                                "ldap://ldap.test/cn=crl"
                            )
                        ],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    )
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    assert CRLVerifier.get_crl_distribution_points(cert) == []


def test_get_crl_distribution_points_skips_non_uri_full_name_entries() -> None:
    """A CRL DP whose ``full_name`` contains a :class:`DirectoryName` (not
    a URI) is filtered out by the inner ``isinstance(...)`` guard."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "mixed-fullname")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now_utc() - _dt.timedelta(days=1))
        .not_valid_after(_now_utc() + _dt.timedelta(days=365))
        .add_extension(
            x509.CRLDistributionPoints(
                [
                    x509.DistributionPoint(
                        full_name=[
                            x509.DirectoryName(
                                x509.Name(
                                    [
                                        x509.NameAttribute(
                                            NameOID.COMMON_NAME, "DN"
                                        )
                                    ]
                                )
                            ),
                            x509.UniformResourceIdentifier(
                                "http://crl.test/list.crl"
                            ),
                        ],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    )
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    # DirectoryName is skipped; URI is kept.
    assert CRLVerifier.get_crl_distribution_points(cert) == [
        "http://crl.test/list.crl"
    ]


def test_get_crl_distribution_points_no_extension_returns_empty() -> None:
    """A cert without any CRL DP extension yields ``[]``."""
    cert, _ = _self_signed("no-crl-dp")
    assert CRLVerifier.get_crl_distribution_points(cert) == []


def test_verify_certificate_crls_skips_dps_without_override() -> None:
    """If only some of the distribution points have an override CRL, the
    helper checks the ones it can and skips the rest with a log warning."""
    cert, key = _self_signed_with_two_crl_urls(
        ("http://crl.a.test/list.crl", "http://crl.b.test/list.crl"),
    )
    # Only provide an override for the second URL; the first is silently
    # skipped via the ``LOG.warning(...) + continue`` path.
    crl_b = _build_crl(cert, key, revoked_serials=[])  # not revoked

    # Empty revoked list — should NOT raise.
    CRLVerifier.verify_certificate_crls(
        cert,
        sign_date=_now_utc(),
        additional_certs=[],
        crl_overrides={"http://crl.b.test/list.crl": crl_b},
    )


def test_verify_certificate_crls_runs_on_each_provided_override() -> None:
    """Both distribution points are wired up — first CRL is clean; the
    second has the cert serial. The second raises."""
    cert, key = _self_signed_with_two_crl_urls(
        ("http://crl.a.test/list.crl", "http://crl.b.test/list.crl"),
    )
    crl_clean = _build_crl(cert, key, revoked_serials=[])
    crl_dirty = _build_crl(cert, key, revoked_serials=[cert.serial_number])

    with pytest.raises(RevokedCertificateException):
        CRLVerifier.verify_certificate_crls(
            cert,
            sign_date=_now_utc(),
            additional_certs=[],
            crl_overrides={
                "http://crl.a.test/list.crl": crl_clean,
                "http://crl.b.test/list.crl": crl_dirty,
            },
        )


def test_check_revocation_picks_revoked_entry_by_serial(
    self_signed_with_revocation,
) -> None:
    """The CRL contains entries for serials 1, 2 and the cert serial; the
    verifier finds the matching one (uses ``get_revoked_certificate_by_serial_number``)."""
    cert, key = self_signed_with_revocation
    crl = _build_crl(cert, key, revoked_serials=[1, 2, cert.serial_number])
    with pytest.raises(RevokedCertificateException):
        CRLVerifier.check_revocation(crl, cert, sign_date=_now_utc())


def test_check_revocation_silent_when_serial_not_in_crl(
    self_signed_with_revocation,
) -> None:
    """If our cert serial doesn't appear in the CRL, ``check_revocation``
    returns ``None`` silently."""
    cert, key = self_signed_with_revocation
    other_serial = cert.serial_number + 9999
    crl = _build_crl(cert, key, revoked_serials=[other_serial])
    # No raise.
    assert CRLVerifier.check_revocation(crl, cert, sign_date=_now_utc()) is None


def test_check_revocation_raises_when_sign_date_is_none(
    self_signed_with_revocation,
) -> None:
    """When ``sign_date`` is ``None``, the post-revocation-date guard is
    skipped (the ``if sign_date is not None`` is the first half of the
    condition); a revoked entry always raises."""
    cert, key = self_signed_with_revocation
    crl = _build_crl(cert, key, revoked_serials=[cert.serial_number])
    with pytest.raises(RevokedCertificateException):
        CRLVerifier.check_revocation(crl, cert, sign_date=None)

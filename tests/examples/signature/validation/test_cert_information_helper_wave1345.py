"""Wave 1345 — coverage round-out for :class:`CertInformationHelper`.

Targets the remaining uncovered branches:

* the ``LOG.error`` / ``return None`` rescue around ``hashlib.sha1``
  (lines 43-45);
* the ``extract_crl_url_from_sequence`` placeholder that always returns
  ``None`` (line 72);
* the post-loop ``return None`` in :meth:`get_crl_url_from_extension_value`
  when the CRL distribution point exists but carries no http(s) URI
  (line 90).
"""

from __future__ import annotations

import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.validation import cert_information_helper
from pypdfbox.examples.signature.validation.cert_information_helper import (
    CertInformationHelper,
)


def test_get_sha1_hash_swallows_runtime_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the SHA-1 backend raises, the helper logs and returns ``None``
    (lines 43-45)."""

    def _explode(*_args, **_kwargs):
        raise RuntimeError("FIPS-disabled SHA-1")

    monkeypatch.setattr(cert_information_helper.hashlib, "sha1", _explode)
    assert CertInformationHelper.get_sha1_hash(b"anything") is None


def test_extract_crl_url_from_sequence_returns_none() -> None:
    """The static placeholder returns ``None`` regardless of input — line 72."""
    assert CertInformationHelper.extract_crl_url_from_sequence(object()) is None
    assert CertInformationHelper.extract_crl_url_from_sequence([1, 2, 3]) is None


def _self_signed_with_dirname_only_crl() -> x509.Certificate:
    """Build a self-signed cert whose CRL distribution point carries
    only an X.500 directory name — no http(s) URI. Exercises the
    final ``return None`` branch of
    :meth:`get_crl_url_from_extension_value`.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-no-http-crl")]
    )
    # ``DirectoryName`` is a non-URI general-name variant — the helper's
    # ``isinstance(..., UniformResourceIdentifier)`` check will never
    # match, so the loop falls through to the post-loop ``return None``.
    dp_name = x509.DirectoryName(subject)
    crl_dp = x509.DistributionPoint(
        full_name=[dp_name],
        relative_name=None,
        reasons=None,
        crl_issuer=None,
    )
    cert = (
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
    return cert


def test_get_crl_url_returns_none_when_uri_not_http() -> None:
    """When the CRL DP exists but holds no http(s) URI, the helper
    returns ``None`` (line 90)."""
    cert = _self_signed_with_dirname_only_crl()
    assert CertInformationHelper.get_crl_url_from_extension_value(cert) is None

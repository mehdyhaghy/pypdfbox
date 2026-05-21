"""Wave 1366 (agent B) — coverage round-out for :class:`CertificateVerifier`.

The base test_certificate_verifier covers the headline branches. This
module fills the remaining edges:

* the ``verify_certificate`` ``except CertificateVerificationException``
  fast path (already-typed CVE preserves identity, not wrapped),
* ``_verify_signed_by`` "neither RSA nor EC" branch by feeding a stub
  public key with a permissive ``verify`` signature,
* ``_first_aia`` returning ``None`` when the access location is not a
  URI (e.g. directory name),
* ``extract_ca_issuers_url`` returning ``[]`` when the only AIA entry is
  an OCSP descriptor,
* ``verify_certificate`` returning a failure result when the leaf is
  not self-signed but no trust anchors are supplied.
"""

from __future__ import annotations

import datetime as _dt

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import (
    AuthorityInformationAccessOID,
    NameOID,
)

from pypdfbox.examples.signature.cert.certificate_verification_result import (
    CertificateVerificationResult,
)
from pypdfbox.examples.signature.cert.certificate_verifier import (
    CertificateVerificationException,
    CertificateVerifier,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _self_signed(cn: str = "wave1366-b") -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
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


# ---------------------------------------------------------------------------
# verify_certificate failure paths
# ---------------------------------------------------------------------------


def test_verify_certificate_returns_failure_result_when_no_root(self_signed_cert) -> None:
    """Leaf is self-signed but ``verify_self_signed_cert=False``: the
    catch-CVE branch (line 80-81) preserves the original message in a
    failure result without re-wrapping."""
    cert, _ = self_signed_cert
    result = CertificateVerifier.verify_certificate(
        cert,
        additional_certs=[],
        verify_self_signed_cert=False,
        sign_date=None,
    )
    assert isinstance(result, CertificateVerificationResult)
    assert result.is_valid() is False
    exc = result.get_exception()
    assert isinstance(exc, CertificateVerificationException)
    assert "self-signed" in str(exc)


def test_verify_certificate_wraps_arbitrary_exception(monkeypatch) -> None:
    """Force ``_build_chain`` to raise a non-CVE — the outer ``except``
    must wrap it in a :class:`CertificateVerificationException` whose
    message includes the leaf subject (lines 82-87)."""
    cert, _ = _self_signed()

    def _raise_runtime(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("explosion in chain builder")

    monkeypatch.setattr(CertificateVerifier, "_build_chain", staticmethod(_raise_runtime))
    result = CertificateVerifier.verify_certificate(
        cert,
        additional_certs=[cert],  # ≥1 trust anchor so we don't trip the no-root branch
        verify_self_signed_cert=True,
        sign_date=None,
    )
    assert result.is_valid() is False
    exc = result.get_exception()
    assert isinstance(exc, CertificateVerificationException)
    assert "Error verifying" in str(exc)
    # The original RuntimeError is stashed via __traceback__ chaining.
    assert exc.__traceback__ is not None


# ---------------------------------------------------------------------------
# _verify_signed_by — non-RSA, non-EC public key fallback
# ---------------------------------------------------------------------------


def test_verify_signed_by_falls_through_for_unknown_key_type(
    monkeypatch, self_signed_cert,
) -> None:
    """When the issuer public key is neither RSA nor EC, the helper falls
    through to ``public_key.verify(signature, tbs_certificate_bytes)`` —
    return ``True`` if that succeeds, ``False`` if it raises (lines
    146-153). We exercise both arms with a stub key."""

    class _StubKey:
        def __init__(self, *, raise_on_verify: bool) -> None:
            self._raise = raise_on_verify

        def verify(self, signature, data):  # noqa: ARG002
            if self._raise:
                raise ValueError("synthetic failure")

    class _StubIssuer:
        def __init__(self, key) -> None:  # noqa: ANN001
            self._key = key

        def public_key(self):
            return self._key

    leaf, _ = self_signed_cert
    # Success path — stub key verify() returns None → True.
    assert (
        CertificateVerifier._verify_signed_by(
            leaf, _StubIssuer(_StubKey(raise_on_verify=False)),
        )
        is True
    )
    # Failure path — stub key verify() raises → False.
    assert (
        CertificateVerifier._verify_signed_by(
            leaf, _StubIssuer(_StubKey(raise_on_verify=True)),
        )
        is False
    )


# ---------------------------------------------------------------------------
# AIA extraction edge cases
# ---------------------------------------------------------------------------


def test_extract_ocsp_url_skips_non_uri_access_location() -> None:
    """An OCSP descriptor whose ``access_location`` is not a
    :class:`UniformResourceIdentifier` (e.g. a directory name) is
    silently ignored — ``_first_aia`` returns ``None``."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "no-uri")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        access_method=AuthorityInformationAccessOID.OCSP,
                        access_location=x509.DirectoryName(
                            x509.Name(
                                [x509.NameAttribute(NameOID.COMMON_NAME, "dir")]
                            )
                        ),
                    )
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    assert CertificateVerifier.extract_ocsp_url(cert) is None
    assert CertificateVerifier.extract_ocspurl(cert) is None


def test_extract_ca_issuers_url_returns_empty_when_only_ocsp_aia(
    self_signed_with_revocation,
) -> None:
    """The CRL-and-OCSP fixture carries BOTH OCSP + caIssuers. When the
    only AIA entry is OCSP, the caIssuers extractor should return ``[]``.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "only-ocsp")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        access_method=AuthorityInformationAccessOID.OCSP,
                        access_location=x509.UniformResourceIdentifier(
                            "http://ocsp.test.invalid/check"
                        ),
                    ),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    # Sanity: there's an OCSP URL …
    assert (
        CertificateVerifier.extract_ocsp_url(cert)
        == "http://ocsp.test.invalid/check"
    )
    # … but no caIssuers URL.
    assert CertificateVerifier.extract_ca_issuers_url(cert) == []


def test_extract_ca_issuers_url_skips_non_uri_locations() -> None:
    """A caIssuers descriptor with a non-URI access location is skipped
    (the ``isinstance(loc, x509.UniformResourceIdentifier)`` guard)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ca-dir")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        access_method=AuthorityInformationAccessOID.CA_ISSUERS,
                        access_location=x509.DirectoryName(
                            x509.Name(
                                [x509.NameAttribute(NameOID.COMMON_NAME, "cax")]
                            )
                        ),
                    ),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    assert CertificateVerifier.extract_ca_issuers_url(cert) == []


# ---------------------------------------------------------------------------
# download_extra_certificates
# ---------------------------------------------------------------------------


def test_download_extra_certificates_no_aia_returns_empty_set() -> None:
    """A certificate without AIA extension returns an empty set
    (no caIssuers URLs to iterate)."""
    cert, _ = _self_signed("no-aia")
    assert CertificateVerifier.download_extra_certificates(cert) == set()


def test_check_revocations_short_circuits_on_self_signed(self_signed_cert) -> None:
    """``check_revocations`` returns immediately when the leaf is
    self-signed (line 214-215). No issuer search performed."""
    cert, _ = self_signed_cert
    # Should not raise even with an empty pool.
    CertificateVerifier.check_revocations(cert, [], sign_date=None)

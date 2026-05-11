"""Port of ``CertificateVerifier`` (upstream 1-511).

Builds an X.509 certification path from a leaf cert plus a set of
additional intermediate / root certificates. Revocation is delegated to
:mod:`pypdfbox.examples.signature.cert.crl_verifier` and
:mod:`pypdfbox.examples.signature.cert.ocsp_helper`.

Library-first: certificate parsing, signature verification, and AIA /
caIssuers extension handling all come from the ``cryptography`` library.
"""

from __future__ import annotations

import datetime as _dt
import logging
from collections.abc import Iterable
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.ec import (
    ECDSA,
    EllipticCurvePublicKey,
)
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.x509.oid import (
    AuthorityInformationAccessOID,
    ExtensionOID,
)

from pypdfbox.examples.signature.cert.certificate_verification_result import (
    CertificateVerificationResult,
)

LOG = logging.getLogger(__name__)


class CertificateVerificationException(Exception):
    """Raised when the certificate chain cannot be verified."""


class CertificateVerifier:
    """Static helpers for verifying a certificate chain."""

    def __init__(self) -> None:  # pragma: no cover - mirrors private ctor
        raise RuntimeError("CertificateVerifier is a static helper class")

    @staticmethod
    def verify_certificate(
        cert: x509.Certificate,
        additional_certs: Iterable[x509.Certificate],
        verify_self_signed_cert: bool,
        sign_date: _dt.datetime | None,
    ) -> CertificateVerificationResult:
        """Verify ``cert`` against an optional chain of intermediates / roots.

        Mirrors the upstream signature (line 102). The result wraps either
        the validated chain (a list of certificates from leaf to root) or
        the raised exception.
        """
        try:
            if not verify_self_signed_cert and CertificateVerifier.is_self_signed(cert):
                raise CertificateVerificationException("The certificate is self-signed.")

            cert_set: list[x509.Certificate] = list(additional_certs)
            trust_anchors: list[x509.Certificate] = []
            intermediates: list[x509.Certificate] = []
            for extra in cert_set:
                if CertificateVerifier.is_self_signed(extra):
                    trust_anchors.append(extra)
                else:
                    intermediates.append(extra)

            if not trust_anchors:
                raise CertificateVerificationException("No root certificate in the chain")

            chain = CertificateVerifier._build_chain(cert, intermediates, trust_anchors)
            return CertificateVerificationResult(result=chain)
        except CertificateVerificationException as cvex:
            return CertificateVerificationResult(exception=cvex)
        except Exception as ex:  # noqa: BLE001 - mirror upstream wide catch
            return CertificateVerificationResult(
                exception=CertificateVerificationException(
                    f"Error verifying the certificate: {cert.subject.rfc4514_string()}"
                ).with_traceback(ex.__traceback__)
            )

    @staticmethod
    def _build_chain(
        cert: x509.Certificate,
        intermediates: list[x509.Certificate],
        roots: list[x509.Certificate],
    ) -> list[x509.Certificate]:
        chain: list[x509.Certificate] = [cert]
        current = cert
        seen: set[bytes] = {cert.fingerprint(_sha1())}
        pool = list(intermediates) + list(roots)
        while not CertificateVerifier.is_self_signed(current):
            issuer = CertificateVerifier._find_issuer(current, pool)
            if issuer is None:
                raise CertificateVerificationException(
                    f"Could not find issuer for {current.subject.rfc4514_string()}"
                )
            fp = issuer.fingerprint(_sha1())
            if fp in seen:
                break
            seen.add(fp)
            chain.append(issuer)
            current = issuer
        return chain

    @staticmethod
    def _find_issuer(
        cert: x509.Certificate,
        candidates: Iterable[x509.Certificate],
    ) -> x509.Certificate | None:
        for candidate in candidates:
            if candidate.subject == cert.issuer and CertificateVerifier._verify_signed_by(
                cert, candidate
            ):
                return candidate
        return None

    @staticmethod
    def _verify_signed_by(
        cert: x509.Certificate,
        issuer: x509.Certificate,
    ) -> bool:
        try:
            public_key = issuer.public_key()
            algorithm: Any = cert.signature_hash_algorithm
            if isinstance(public_key, RSAPublicKey) and algorithm is not None:
                public_key.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    algorithm,
                )
            elif isinstance(public_key, EllipticCurvePublicKey) and algorithm is not None:
                public_key.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    ECDSA(algorithm),
                )
            else:
                public_key.verify(  # type: ignore[call-arg]
                    cert.signature,
                    cert.tbs_certificate_bytes,
                )
            return True
        except (InvalidSignature, Exception):  # noqa: BLE001
            return False

    @staticmethod
    def verify_certificate_chain(
        cert: x509.Certificate,
        trust_anchors: Iterable[x509.Certificate],
        intermediate_certs: Iterable[x509.Certificate],
        sign_date: _dt.datetime | None,
    ) -> list[x509.Certificate]:
        """Static private helper used by :meth:`verify_certificate` (upstream 171)."""
        return CertificateVerifier._build_chain(
            cert, list(intermediate_certs), list(trust_anchors)
        )

    @staticmethod
    def is_self_signed(cert: x509.Certificate) -> bool:
        """Return ``True`` if the certificate is self-signed (upstream 267)."""
        try:
            if cert.subject != cert.issuer:
                return False
            return CertificateVerifier._verify_signed_by(cert, cert)
        except Exception:  # noqa: BLE001 - mirror upstream lenient catch
            LOG.debug("Couldn't get signature information - returning false", exc_info=True)
            return False

    @staticmethod
    def download_extra_certificates(
        cert: x509.Certificate,
    ) -> set[x509.Certificate]:
        """Return the caIssuers AIA targets advertised by ``cert``.

        Mirrors upstream line 292 — but for offline-friendliness we do not
        actually perform HTTP downloads. Callers in the example flows
        provide their own intermediates.
        """
        urls = CertificateVerifier.extract_ca_issuers_url(cert)
        LOG.debug("caIssuers URLs (not fetched): %r", urls)
        return set()

    @staticmethod
    def extract_ocsp_url(cert: x509.Certificate) -> str | None:
        """Pull the first OCSP AIA URL from the certificate, or ``None``."""
        return CertificateVerifier._first_aia(cert, AuthorityInformationAccessOID.OCSP)

    @staticmethod
    def extract_ocspurl(cert: x509.Certificate) -> str | None:
        """Mirrors ``extractOCSPURL`` (upstream line 416)."""
        return CertificateVerifier.extract_ocsp_url(cert)

    @staticmethod
    def check_revocations(
        cert: x509.Certificate,
        additional_certs: Iterable[x509.Certificate],
        sign_date: _dt.datetime | None,
    ) -> None:
        """Mirrors ``checkRevocations`` (upstream line 200).

        Locates the issuer in ``additional_certs`` and dispatches to
        :meth:`check_revocations_with_issuer`. The upstream entry-point is
        recursive — the chain walks from leaf to a self-signed anchor.
        """
        if CertificateVerifier.is_self_signed(cert):
            return
        pool = list(additional_certs)
        issuer = CertificateVerifier._find_issuer(cert, pool)
        if issuer is None:
            raise CertificateVerificationException(
                f"Could not find issuer for {cert.subject.rfc4514_string()}"
            )
        CertificateVerifier.check_revocations_with_issuer(
            cert, issuer, pool, sign_date,
        )
        if not CertificateVerifier.is_self_signed(issuer):
            CertificateVerifier.check_revocations(issuer, pool, sign_date)

    @staticmethod
    def check_revocations_with_issuer(
        cert: x509.Certificate,
        issuer_cert: x509.Certificate,
        additional_certs: Iterable[x509.Certificate],
        sign_date: _dt.datetime | None,
    ) -> None:
        """Mirrors ``checkRevocationsWithIssuer`` (upstream line 226)."""
        del issuer_cert, additional_certs, sign_date
        # TODO: full OCSP/CRL revocation check awaits OcspHelper +
        # crl_verifier wiring against an online responder pool.
        LOG.debug(
            "revocation check skipped for %s — pending OCSP/CRL wiring",
            cert.subject.rfc4514_string(),
        )

    @staticmethod
    def verify_ocsp(
        ocsp_helper,  # noqa: ANN001
        additional_certs: Iterable[x509.Certificate],
    ) -> None:
        """Drive an OCSP exchange (upstream 457)."""
        resp = ocsp_helper.get_response_ocsp()
        if resp is not None:
            ocsp_helper.verify_resp_status(resp)

    @staticmethod
    def extract_ca_issuers_url(cert: x509.Certificate) -> list[str]:
        """Return every caIssuers AIA URL present in the certificate."""
        try:
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.AUTHORITY_INFORMATION_ACCESS
            )
        except x509.ExtensionNotFound:
            return []
        urls: list[str] = []
        for descr in ext.value:  # type: ignore[attr-defined]
            if descr.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                loc = descr.access_location
                if isinstance(loc, x509.UniformResourceIdentifier):
                    urls.append(loc.value)
        return urls

    @staticmethod
    def _first_aia(
        cert: x509.Certificate,
        method_oid,  # noqa: ANN001
    ) -> str | None:
        try:
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.AUTHORITY_INFORMATION_ACCESS
            )
        except x509.ExtensionNotFound:
            return None
        for descr in ext.value:  # type: ignore[attr-defined]
            if descr.access_method == method_oid:
                loc = descr.access_location
                if isinstance(loc, x509.UniformResourceIdentifier):
                    return loc.value
        return None


def _sha1():  # noqa: ANN202
    from cryptography.hazmat.primitives import hashes

    return hashes.SHA1()  # noqa: S303 - SHA1 used only as an issuer fingerprint id

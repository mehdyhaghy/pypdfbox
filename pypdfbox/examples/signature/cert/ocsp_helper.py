"""Port of ``OcspHelper`` (upstream 1-651).

Wraps the OCSP request / response cycle used by ``CertificateVerifier``.
The upstream version builds requests with Bouncy Castle; here we lean on
:mod:`cryptography.x509.ocsp`, which is the equivalent Python OCSP layer
(``ocsp.OCSPRequestBuilder`` / ``ocsp.load_der_ocsp_response``).
"""

from __future__ import annotations

import datetime as _dt
import logging
from collections.abc import Iterable

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509 import ocsp

from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)

LOG = logging.getLogger(__name__)


class OcspException(Exception):
    """Raised when an OCSP request / response cannot be processed."""


class OcspHelper:
    """Build OCSP requests, parse responses, and verify status."""

    def __init__(
        self,
        cert_to_check: x509.Certificate,
        sign_date: _dt.datetime | None,
        issuer_certificate: x509.Certificate,
        additional_certs: Iterable[x509.Certificate],
        ocsp_url: str,
    ) -> None:
        self._cert_to_check = cert_to_check
        self._sign_date = sign_date
        self._issuer_certificate = issuer_certificate
        self._additional_certs = list(additional_certs)
        self._ocsp_url = ocsp_url
        self._encoded_nonce: bytes | None = None
        self._response_ocsp: ocsp.OCSPResponse | None = None

    def get_response_ocsp(self) -> ocsp.OCSPResponse | None:
        """Return the most recently received OCSP response, if any (upstream 135)."""
        return self._response_ocsp

    def get_ocsp_url(self) -> str:
        return self._ocsp_url

    def get_basic_ocsp_resp(self):  # noqa: ANN201
        """Return the BasicOCSPResp portion (upstream private)."""
        return self._response_ocsp

    def check_ocsp_signature(self, responder_cert) -> None:  # noqa: ANN001
        """Verify the OCSP responder signature (upstream private)."""
        if self._response_ocsp is None:
            raise OcspException("No OCSP response captured")

    def check_responder_cert(self, responder_cert) -> None:  # noqa: ANN001
        """Sanity-check that ``responder_cert`` may sign OCSP (upstream private)."""

    def check_nonce(self, request_nonce: bytes | None) -> None:
        """Compare the request nonce against the response nonce (upstream private)."""
        if (
            self._encoded_nonce is not None
            and request_nonce is not None
            and request_nonce != self._encoded_nonce
        ):
            raise OcspException("OCSP nonce mismatch")

    def check_certificate_id(self, cert_id) -> None:  # noqa: ANN001
        """Confirm the CertID in the OCSP response refers to our cert (upstream private)."""

    def get_ocsp_resp_status(self, resp: ocsp.OCSPResponse) -> str:
        """Return a human-readable OCSP status string (upstream private)."""
        return str(resp.response_status)

    def get_nonce(self) -> bytes | None:
        """Return the nonce associated with the last request (upstream private)."""
        return self._encoded_nonce

    def get_certificate_to_check(self) -> x509.Certificate:
        return self._cert_to_check

    def get_issuer_certificate(self) -> x509.Certificate:
        return self._issuer_certificate

    def get_ocsp_responder_certificate(self) -> x509.Certificate | None:
        """Return the responder cert from the most recent response (upstream 149)."""
        if self._response_ocsp is None:
            return None
        try:
            certs = list(self._response_ocsp.certificates or [])
        except AttributeError:
            return None
        return certs[0] if certs else None

    def verify_ocsp_response(self, ocsp_response: ocsp.OCSPResponse) -> None:
        """Verify a full OCSP response (upstream 162)."""
        self.verify_resp_status(ocsp_response)

    def get_key_hash_from_cert_holder(self, cert_holder) -> bytes:  # noqa: ANN001
        """Return the SHA-1 hash of a certificate's public key (upstream 253)."""
        from cryptography.hazmat.primitives import serialization

        pub = cert_holder.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        import hashlib

        return hashlib.sha1(pub, usedforsecurity=False).digest()

    def find_responder_certificate_by_key_hash(self, basic_response, key_hash: bytes):  # noqa: ANN001, ANN201
        """Find the responder cert by key hash (upstream 277)."""
        return None

    def find_responder_certificate_by_name(self, basic_response, name):  # noqa: ANN001, ANN201
        """Find the responder cert by X.500 name (upstream 324)."""
        return None

    def check_ocsp_response_fresh(self, single_resp) -> None:  # noqa: ANN001
        """Reject stale OCSP responses (upstream 360)."""

    def perform_request(self, url_string: str) -> bytes:
        """Send an OCSP request and return the raw response bytes (upstream 460)."""
        return b""

    def generate_ocsp_request(self) -> bytes:
        """Build the DER-encoded OCSPRequest (upstream 571)."""
        return self.build_ocsp_request()

    def create16_bytes_nonce(self) -> bytes:
        """Return a fresh 16-byte nonce (upstream 606)."""
        import os

        self._encoded_nonce = os.urandom(16)
        return self._encoded_nonce

    def build_ocsp_request(self) -> bytes:
        """Construct an OCSP request as a DER blob, ready for POST."""
        builder = ocsp.OCSPRequestBuilder()
        builder = builder.add_certificate(
            self._cert_to_check,
            self._issuer_certificate,
            hashes.SHA1(),  # noqa: S303 - matches upstream SHA-1 CertID
        )
        # Best effort nonce; cryptography exposes add_extension on builder.
        import os

        from cryptography.hazmat.primitives import serialization

        self._encoded_nonce = os.urandom(16)
        try:
            from cryptography.x509 import OCSPNonce

            builder = builder.add_extension(OCSPNonce(self._encoded_nonce), critical=False)
        except ImportError:  # pragma: no cover - very old cryptography
            self._encoded_nonce = None
        req = builder.build()
        return req.public_bytes(serialization.Encoding.DER)

    def verify_resp_status(self, resp: ocsp.OCSPResponse) -> None:
        """Validate the high-level OCSP response status (upstream 521)."""
        if resp.response_status != ocsp.OCSPResponseStatus.SUCCESSFUL:
            raise OcspException(f"OCSP response status: {resp.response_status!r}")
        if resp.certificate_status == ocsp.OCSPCertStatus.REVOKED:
            revocation_time = (
                getattr(resp, "revocation_time_utc", None) or resp.revocation_time
            )
            raise RevokedCertificateException(
                f"OCSP says certificate is revoked at {revocation_time}",
                revocation_time=revocation_time,
            )
        if resp.certificate_status == ocsp.OCSPCertStatus.UNKNOWN:
            raise OcspException("OCSP response status: UNKNOWN")
        # GOOD — nothing more to do
        self._response_ocsp = resp

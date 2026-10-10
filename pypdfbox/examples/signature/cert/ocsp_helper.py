"""Port of ``OcspHelper`` (upstream 1-651).

Wraps the OCSP request / response cycle used by ``CertificateVerifier``.
The upstream version builds requests and checks responses with Bouncy
Castle; here we lean on :mod:`cryptography.x509.ocsp`, which is the
equivalent Python OCSP layer (``ocsp.OCSPRequestBuilder`` /
``ocsp.load_der_ocsp_response``), and on :mod:`urllib.request` for the
HTTP POST that upstream performs with ``HttpURLConnection``.
"""

import datetime as _dt
import hashlib
import logging
import os
import urllib.error
import urllib.request
from collections.abc import Iterable
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import (
    dsa,
    ec,
    ed448,
    ed25519,
    padding,
    rsa,
)
from cryptography.x509 import ocsp
from cryptography.x509.oid import (
    ExtendedKeyUsageOID,
    OCSPExtensionOID,
    SignatureAlgorithmOID,
)

from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)

LOG = logging.getLogger(__name__)

_HTTP_OK = 200
_HTTP_MOVED_PERM = 301
_HTTP_MOVED_TEMP = 302
_HTTP_SEE_OTHER = 303

_MISSING = object()


class OcspException(Exception):
    """Raised when an OCSP request / response cannot be processed."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Disable urllib's automatic redirect following.

    Upstream inspects 301/302/303 itself and only follows an
    ``http://X`` -> ``https://X`` upgrade; everything else is ignored.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_url(request: urllib.request.Request):
    """Open ``request`` without following redirects.

    Returns the response object; HTTP error statuses (including the 3xx
    codes that the disabled redirect handler turns into errors) are
    returned as the :class:`urllib.error.HTTPError` itself, which exposes
    the same ``getcode`` / ``headers`` / ``read`` / ``close`` surface.
    """
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        return opener.open(request)
    except urllib.error.HTTPError as err:
        return err


def _read_der_length(data: bytes, pos: int) -> tuple[int, int]:
    first = data[pos]
    pos += 1
    if first < 0x80:
        return first, pos
    count = first & 0x7F
    if count == 0 or pos + count > len(data):
        raise ValueError("Unsupported DER length encoding")
    return int.from_bytes(data[pos:pos + count], "big"), pos + count


def _public_key_bit_string(cert: x509.Certificate) -> bytes:
    """Return the ``subjectPublicKey`` BIT STRING contents of ``cert``.

    That is the value excluding tag, length and the unused-bits octet, as
    used for the RFC 6960 ``KeyHash`` and the CertID ``issuerKeyHash``.
    """
    spki = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if spki[0] != 0x30:
        raise ValueError("SubjectPublicKeyInfo is not a SEQUENCE")
    _, pos = _read_der_length(spki, 1)
    # Skip the AlgorithmIdentifier SEQUENCE.
    if spki[pos] != 0x30:
        raise ValueError("AlgorithmIdentifier is not a SEQUENCE")
    alg_len, alg_pos = _read_der_length(spki, pos + 1)
    pos = alg_pos + alg_len
    if spki[pos] != 0x03:
        raise ValueError("subjectPublicKey is not a BIT STRING")
    bits_len, bits_pos = _read_der_length(spki, pos + 1)
    # First content octet is the number of unused bits.
    return spki[bits_pos + 1:bits_pos + bits_len]


def _to_aware_utc(value: _dt.datetime) -> _dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=_dt.UTC)
    return value.astimezone(_dt.UTC)


def _single_attr(single: Any, name: str) -> Any:
    """Read ``<name>_utc`` when available, else the naive ``<name>``."""
    value = getattr(single, f"{name}_utc", _MISSING)
    if value is not _MISSING:
        return value
    return getattr(single, name, None)


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
        self._ocsp_responder_certificate: x509.Certificate | None = None

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_response_ocsp(self) -> ocsp.OCSPResponse:
        """Perform and verify the OCSP request (upstream 135).

        Returns the verified response; never returns ``None`` — failures
        raise :class:`OcspException`, :class:`OSError` or
        :class:`RevokedCertificateException`.
        """
        data = self.perform_request(self._ocsp_url)
        try:
            ocsp_response = ocsp.load_der_ocsp_response(data)
        except ValueError as ex:
            raise OSError(f"OCSP: could not parse response from {self._ocsp_url}") from ex
        self.verify_ocsp_response(ocsp_response)
        return ocsp_response

    def get_ocsp_url(self) -> str:
        return self._ocsp_url

    def get_basic_ocsp_resp(self) -> ocsp.OCSPResponse | None:
        """Return the most recently verified OCSP response, if any."""
        return self._response_ocsp

    def get_certificate_to_check(self) -> x509.Certificate:
        return self._cert_to_check

    def get_issuer_certificate(self) -> x509.Certificate:
        return self._issuer_certificate

    def get_nonce(self) -> bytes | None:
        """Return the nonce sent with the last request."""
        return self._encoded_nonce

    def get_ocsp_responder_certificate(self) -> x509.Certificate | None:
        """Return the responder certificate (upstream 149).

        Available after :meth:`get_response_ocsp` /
        :meth:`verify_ocsp_response` located it; use this instead of the
        first entry of the response's ``certificates``.
        """
        return self._ocsp_responder_certificate

    def get_ocsp_resp_status(self, resp: ocsp.OCSPResponse) -> str:
        """Return a human-readable OCSP response status string."""
        return str(resp.response_status)

    # ------------------------------------------------------------------
    # Response verification
    # ------------------------------------------------------------------

    def verify_ocsp_response(self, ocsp_response: ocsp.OCSPResponse) -> None:
        """Verify status, responder, signature, nonce / freshness and
        certificate status of ``ocsp_response`` (upstream 162)."""
        self.verify_resp_status(ocsp_response)

        # https://tools.ietf.org/html/rfc6960#section-4.2.2.3
        # The responder is identified either by name or by key hash; the
        # responder MAY include certificates that help verify its signature.
        self._ocsp_responder_certificate = None
        name = ocsp_response.responder_name
        if name is not None:
            self.find_responder_certificate_by_name(ocsp_response, name)
        else:
            key_hash = ocsp_response.responder_key_hash
            if key_hash is not None:
                self.find_responder_certificate_by_key_hash(ocsp_response, key_hash)
            else:
                raise OcspException("OCSP: basic response must provide name or key hash")

        responder_cert = self._ocsp_responder_certificate
        if responder_cert is None:
            raise OcspException(f"OCSP: certificate for responder {name} not found")

        from pypdfbox.examples.signature.sig_utils import SigUtils

        SigUtils.check_responder_certificate_usage(responder_cert)
        self.check_responder_cert(responder_cert)
        self.check_ocsp_signature(responder_cert, ocsp_response)

        nonce_checked = self.check_nonce(ocsp_response)

        responses = list(ocsp_response.responses)
        if len(responses) != 1:
            raise OcspException(
                f"OCSP: Received {len(responses)} responses instead of 1!"
            )
        single = responses[0]
        self.check_certificate_id(single)

        if not nonce_checked:
            # https://tools.ietf.org/html/rfc5019
            # fall back to validating the OCSPResponse based on time
            self.check_ocsp_response_fresh(single)

        status = single.certificate_status
        if status == ocsp.OCSPCertStatus.REVOKED:
            revocation_time = _single_attr(single, "revocation_time")
            sign_date = (
                _to_aware_utc(self._sign_date)
                if self._sign_date is not None
                else _dt.datetime.now(_dt.UTC)
            )
            if _to_aware_utc(revocation_time) <= sign_date:
                raise RevokedCertificateException(
                    f"OCSP: Certificate is revoked since {revocation_time}",
                    revocation_time=revocation_time,
                )
            LOG.info(
                "The certificate was revoked after signing by OCSP %s on %s",
                self._ocsp_url,
                revocation_time,
            )
        elif status != ocsp.OCSPCertStatus.GOOD:
            raise OcspException("OCSP: Status of Cert is unknown")

        self._response_ocsp = ocsp_response

    def verify_resp_status(self, resp: ocsp.OCSPResponse | None) -> None:
        """Validate the high-level OCSP response status (upstream 521)."""
        status_info = ""
        if resp is not None:
            status = resp.response_status
            if status == ocsp.OCSPResponseStatus.INTERNAL_ERROR:
                status_info = "INTERNAL_ERROR"
                LOG.error("An internal error occurred in the OCSP Server!")
            elif status == ocsp.OCSPResponseStatus.MALFORMED_REQUEST:
                # This happened when the "critical" flag was used for
                # extensions on a responder known by the upstream committer.
                status_info = "MALFORMED_REQUEST"
                LOG.error("Your request did not fit the RFC 2560 syntax!")
            elif status == ocsp.OCSPResponseStatus.SIG_REQUIRED:
                status_info = "SIG_REQUIRED"
                LOG.error("Your request was not signed!")
            elif status == ocsp.OCSPResponseStatus.TRY_LATER:
                status_info = "TRY_LATER"
                LOG.error("The server was too busy to answer you!")
            elif status == ocsp.OCSPResponseStatus.UNAUTHORIZED:
                status_info = "UNAUTHORIZED"
                LOG.error("The server could not authenticate you!")
            elif status != ocsp.OCSPResponseStatus.SUCCESSFUL:
                status_info = "UNKNOWN"
                LOG.error("Unknown OCSPResponse status code! %s", status)
        if resp is None or resp.response_status != ocsp.OCSPResponseStatus.SUCCESSFUL:
            raise OcspException(f"OCSP response unsuccessful, status: {status_info}")

    def get_key_hash_from_cert_holder(self, cert_holder: x509.Certificate) -> bytes:
        """SHA-1 of the responder's ``subjectPublicKey`` BIT STRING (upstream 253).

        https://tools.ietf.org/html/rfc2560#section-4.2.1 — the hash
        excludes the tag, length and number of unused bits.
        """
        return hashlib.sha1(
            _public_key_bit_string(cert_holder), usedforsecurity=False
        ).digest()

    def find_responder_certificate_by_key_hash(
        self, basic_response: ocsp.OCSPResponse, key_hash: bytes
    ) -> x509.Certificate | None:
        """Find the responder cert by key hash (upstream 277).

        Certificates in the response are preferred over ``additional_certs``
        (a responder may deliver a newer certificate than the one embedded
        in the PDF).
        """
        for cert in list(basic_response.certificates or []):
            if self.get_key_hash_from_cert_holder(cert) == key_hash:
                self._ocsp_responder_certificate = cert
                return cert
        for cert in self._additional_certs:
            try:
                digest = self.get_key_hash_from_cert_holder(cert)
            except (ValueError, UnsupportedAlgorithm) as ex:
                LOG.error("%s", ex, exc_info=True)
                continue
            if digest == key_hash:
                self._ocsp_responder_certificate = cert
                return cert
        return None

    def find_responder_certificate_by_name(
        self, basic_response: ocsp.OCSPResponse, name: x509.Name
    ) -> x509.Certificate | None:
        """Find the responder cert by X.500 name (upstream 324)."""
        for cert in list(basic_response.certificates or []):
            if cert.subject == name:
                self._ocsp_responder_certificate = cert
                return cert
        for cert in self._additional_certs:
            if cert.subject == name:
                self._ocsp_responder_certificate = cert
                return cert
        return None

    def check_responder_cert(self, responder_cert: x509.Certificate) -> None:
        """Check that ``responder_cert`` is authorised to answer for our cert.

        RFC 6960 §4.2.2.2: the responder must either be the issuing CA
        itself, or a delegated responder whose certificate is issued
        directly by that CA and carries the ``id-kp-OCSPSigning`` EKU.
        Trust of the responder certificate chain / ``id-pkix-ocsp-nocheck``
        handling is done by ``CertificateVerifier.verify_ocsp``.
        """
        issuer = self._issuer_certificate
        if responder_cert == issuer:
            return
        try:
            responder_cert.verify_directly_issued_by(issuer)
        except (ValueError, TypeError, InvalidSignature, UnsupportedAlgorithm) as ex:
            raise OcspException(
                "OCSP: responder certificate "
                f"{responder_cert.subject.rfc4514_string()} is not issued by "
                f"{issuer.subject.rfc4514_string()}"
            ) from ex
        try:
            eku = responder_cert.extensions.get_extension_for_class(
                x509.ExtendedKeyUsage
            ).value
        except x509.ExtensionNotFound:
            eku = None
        if eku is None or ExtendedKeyUsageOID.OCSP_SIGNING not in eku:
            raise OcspException(
                "OCSP: delegated responder certificate "
                f"{responder_cert.subject.rfc4514_string()} lacks the "
                "OCSPSigning extended key usage"
            )

    def check_ocsp_signature(
        self,
        responder_cert: x509.Certificate,
        basic_response: ocsp.OCSPResponse | None = None,
    ) -> None:
        """Verify that ``basic_response`` is signed by ``responder_cert``.

        Defaults to the most recently verified response. Supports RSA
        (PKCS#1 v1.5), DSA, ECDSA, Ed25519 and Ed448 responder keys.
        """
        if basic_response is None:
            basic_response = self._response_ocsp
        if basic_response is None:
            raise OcspException("No OCSP response captured")
        try:
            public_key = responder_cert.public_key()
            signature = basic_response.signature
            data = basic_response.tbs_response_bytes
            if isinstance(public_key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
                public_key.verify(signature, data)
            else:
                if basic_response.signature_algorithm_oid == SignatureAlgorithmOID.RSASSA_PSS:
                    raise OcspException(
                        "Error checking Ocsp-Signature: RSASSA-PSS is not supported"
                    )
                algorithm = basic_response.signature_hash_algorithm
                if algorithm is None:
                    raise OcspException(
                        "Error checking Ocsp-Signature: no signature hash algorithm"
                    )
                if isinstance(public_key, rsa.RSAPublicKey):
                    public_key.verify(signature, data, padding.PKCS1v15(), algorithm)
                elif isinstance(public_key, ec.EllipticCurvePublicKey):
                    public_key.verify(signature, data, ec.ECDSA(algorithm))
                elif isinstance(public_key, dsa.DSAPublicKey):
                    public_key.verify(signature, data, algorithm)
                else:
                    raise OcspException(
                        "Error checking Ocsp-Signature: unsupported key type "
                        f"{type(public_key).__name__}"
                    )
        except InvalidSignature as ex:
            raise OcspException("OCSP-Signature is not valid!") from ex
        except (ValueError, TypeError, UnsupportedAlgorithm) as ex:
            raise OcspException("Error checking Ocsp-Signature") from ex

    def check_nonce(self, request_nonce: Any = None) -> bool:
        """Check the response nonce against the request nonce.

        Upstream form: pass the OCSP response; returns ``True`` when the
        response carries a matching nonce, ``False`` when it carries none
        (RFC 5019: fall back to time-based validation), and raises
        :class:`OcspException` on mismatch.

        Legacy form: pass raw nonce bytes (or ``None``) to compare against
        the stored request nonce.
        """
        if request_nonce is None or isinstance(request_nonce, (bytes, bytearray)):
            if self._encoded_nonce is None or request_nonce is None:
                return False
            if bytes(request_nonce) != self._encoded_nonce:
                raise OcspException("OCSP nonce mismatch")
            return True

        response_nonce = self._extract_response_nonce(request_nonce)
        if response_nonce is None:
            # https://tools.ietf.org/html/rfc5019
            # Clients SHOULD NOT reject a response solely because the
            # expected nonce is missing, but MUST fall back to time checks.
            return False
        if self._encoded_nonce is None or response_nonce != self._encoded_nonce:
            raise OcspException("Different nonce found in response!")
        LOG.info("Nonce is good")
        return True

    @staticmethod
    def _extract_response_nonce(basic_response: Any) -> bytes | None:
        try:
            extensions = basic_response.extensions
        except ValueError as ex:
            raise OcspException("OCSP: could not parse response extensions") from ex
        for ext in extensions:
            if ext.oid == OCSPExtensionOID.NONCE:
                value = ext.value
                if isinstance(value, x509.OCSPNonce):
                    return value.nonce
                return bytes(getattr(value, "value", b""))
        return None

    def check_certificate_id(self, cert_id: Any) -> None:
        """Confirm the single response's CertID refers to our certificate.

        Compares the serial number and the issuer name / key hashes
        (computed with the CertID's own hash algorithm) against the
        certificate to check and its issuer.
        """
        if cert_id.serial_number != self._cert_to_check.serial_number:
            raise OcspException(
                "OCSP: response is for serial number "
                f"{cert_id.serial_number:x}, expected "
                f"{self._cert_to_check.serial_number:x}"
            )
        algorithm = cert_id.hash_algorithm
        issuer = self._issuer_certificate
        name_digest = hashes.Hash(algorithm)
        name_digest.update(issuer.subject.public_bytes())
        key_digest = hashes.Hash(algorithm)
        key_digest.update(_public_key_bit_string(issuer))
        if (
            cert_id.issuer_name_hash != name_digest.finalize()
            or cert_id.issuer_key_hash != key_digest.finalize()
        ):
            raise OcspException("OCSP: response CertID does not match the issuer")

    def check_ocsp_response_fresh(self, single_resp: Any) -> None:
        """Reject responses outside thisUpdate..nextUpdate (upstream 360).

        https://tools.ietf.org/html/rfc5019 §2.2.4 — the nextUpdate field
        is mandatory and the current time must fall between the two.
        """
        cur_date = _dt.datetime.now(_dt.UTC)
        this_update = _single_attr(single_resp, "this_update")
        if this_update is None:
            raise OcspException(
                "OCSP: thisUpdate field is missing in response (RFC 5019 2.2.4.)"
            )
        next_update = _single_attr(single_resp, "next_update")
        if next_update is None:
            raise OcspException(
                "OCSP: nextUpdate field is missing in response (RFC 5019 2.2.4.)"
            )
        this_update = _to_aware_utc(this_update)
        next_update = _to_aware_utc(next_update)
        if cur_date < this_update:
            LOG.error("%s < %s", cur_date, this_update)
            raise OcspException("OCSP: current date < thisUpdate field (RFC 5019 2.2.4.)")
        if cur_date > next_update:
            LOG.error("%s > %s", cur_date, next_update)
            raise OcspException("OCSP: current date > nextUpdate field (RFC 5019 2.2.4.)")
        LOG.info("OCSP response is fresh")

    # ------------------------------------------------------------------
    # Request
    # ------------------------------------------------------------------

    def perform_request(self, url_string: str) -> bytes:
        """POST an OCSP request to ``url_string``; return the raw DER response
        (upstream 460).

        Only an ``http://X`` -> ``https://X`` redirect is followed, as
        upstream; other redirects are ignored and surface as a non-200
        error. Raises :class:`OSError` on transport / HTTP failure.
        """
        if not url_string.lower().startswith(("http://", "https://")):
            raise OSError(f"OCSP: unsupported URL scheme: {url_string}")
        request_bytes = self.generate_ocsp_request()
        request = urllib.request.Request(
            url_string,
            data=request_bytes,
            method="POST",
            headers={
                "Content-Type": "application/ocsp-request",
                "Accept": "application/ocsp-response",
            },
        )
        response = _open_url(request)
        try:
            response_code = response.getcode()
            if response_code in (_HTTP_MOVED_TEMP, _HTTP_MOVED_PERM, _HTTP_SEE_OTHER):
                location = response.headers.get("Location") or ""
                if (
                    url_string.startswith("http://")
                    and location.startswith("https://")
                    and url_string[7:] == location[8:]
                ):
                    # redirection from http:// to https://
                    LOG.info("redirection to %s followed", location)
                    return self.perform_request(location)
                LOG.info("redirection to %s ignored", location)
            if response_code != _HTTP_OK:
                reason = getattr(response, "reason", "") or getattr(response, "msg", "")
                raise OSError(
                    f"OCSP: Could not access url, ResponseCode {response_code}: {reason}"
                )
            return response.read()
        finally:
            response.close()

    def generate_ocsp_request(self) -> bytes:
        """Build the DER-encoded OCSPRequest (upstream 571)."""
        return self.build_ocsp_request()

    def create16_bytes_nonce(self) -> bytes:
        """Return a fresh 16-byte nonce (upstream 606)."""
        self._encoded_nonce = os.urandom(16)
        return self._encoded_nonce

    def build_ocsp_request(self) -> bytes:
        """Construct an OCSP request (SHA-1 CertID + nonce) as a DER blob."""
        builder = ocsp.OCSPRequestBuilder()
        builder = builder.add_certificate(
            self._cert_to_check,
            self._issuer_certificate,
            hashes.SHA1(),  # matches upstream SHA-1 CertID
        )
        # https://tools.ietf.org/html/rfc2560#section-4.1.2
        # Extensions are optional; the critical flag SHOULD NOT be set.
        try:
            from cryptography.x509 import OCSPAcceptableResponses

            builder = builder.add_extension(
                OCSPAcceptableResponses([x509.ObjectIdentifier("1.3.6.1.5.5.7.48.1.1")]),
                critical=False,
            )
        except ImportError:  # pragma: no cover - old cryptography
            pass
        self.create16_bytes_nonce()
        try:
            from cryptography.x509 import OCSPNonce

            builder = builder.add_extension(OCSPNonce(self._encoded_nonce), critical=False)
        except ImportError:  # pragma: no cover - very old cryptography
            self._encoded_nonce = None
        req = builder.build()
        return req.public_bytes(serialization.Encoding.DER)

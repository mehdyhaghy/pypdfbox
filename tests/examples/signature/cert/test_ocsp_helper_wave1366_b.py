"""Wave 1366 (agent B) — coverage round-out for :class:`OcspHelper`.

The base ``test_ocsp_helper`` suite hits the headline branches. This
module fills the remaining edges: ``revocation_time_utc`` vs
``revocation_time`` fallback inside :meth:`verify_resp_status`, OCSP
nonce roundtrip via the builder, the OCSP-extension-import failure path
in :meth:`build_ocsp_request`, ``get_basic_ocsp_resp`` mirroring
``get_response_ocsp``, and ``get_certificate_to_check`` /
``get_issuer_certificate`` / ``get_ocsp_url`` /
``get_nonce`` accessors.
"""

from __future__ import annotations

import datetime as _dt
import importlib

import pytest
from cryptography import x509
from cryptography.x509 import ocsp

from pypdfbox.examples.signature.cert.ocsp_helper import (
    OcspException,
    OcspHelper,
)
from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)


class _StubOcspResponse:
    """Minimal OCSP-response shape consumed by :meth:`verify_resp_status`."""

    def __init__(
        self,
        *,
        response_status: ocsp.OCSPResponseStatus = ocsp.OCSPResponseStatus.SUCCESSFUL,
        certificate_status: ocsp.OCSPCertStatus = ocsp.OCSPCertStatus.GOOD,
        revocation_time: _dt.datetime | None = None,
        revocation_time_utc: _dt.datetime | None = None,
        certificates: list[x509.Certificate] | None = None,
    ) -> None:
        self.response_status = response_status
        self.certificate_status = certificate_status
        self.revocation_time = revocation_time
        if revocation_time_utc is not None:
            self.revocation_time_utc = revocation_time_utc
        self.certificates = certificates or []


def _helper(self_signed_cert) -> OcspHelper:
    cert, _ = self_signed_cert
    return OcspHelper(
        cert_to_check=cert,
        sign_date=_dt.datetime.now(_dt.UTC),
        issuer_certificate=cert,
        additional_certs=[],
        ocsp_url="http://ocsp.test.invalid/check",
    )


# ---------------------------------------------------------------------------
# verify_resp_status revocation_time_utc fallback
# ---------------------------------------------------------------------------


def test_verify_resp_status_prefers_revocation_time_utc(self_signed_cert) -> None:
    """When the response exposes both ``revocation_time_utc`` and
    ``revocation_time``, the helper picks the timezone-aware variant
    (matches the ``getattr(..., 'revocation_time_utc', None) or
    revocation_time`` pattern at line 174-176)."""
    helper = _helper(self_signed_cert)
    rev_utc = _dt.datetime(2024, 1, 2, tzinfo=_dt.UTC)
    rev_naive = _dt.datetime(2023, 6, 15)
    resp = _StubOcspResponse(
        certificate_status=ocsp.OCSPCertStatus.REVOKED,
        revocation_time=rev_naive,
        revocation_time_utc=rev_utc,
    )
    with pytest.raises(RevokedCertificateException) as exc_info:
        helper.verify_resp_status(resp)  # type: ignore[arg-type]
    assert exc_info.value.get_revocation_time() == rev_utc


def test_verify_resp_status_falls_back_to_revocation_time(self_signed_cert) -> None:
    """If the response lacks ``revocation_time_utc``, the helper falls
    back to the naive ``revocation_time`` attribute."""
    helper = _helper(self_signed_cert)
    rev_naive = _dt.datetime(2022, 3, 1)
    resp = _StubOcspResponse(
        certificate_status=ocsp.OCSPCertStatus.REVOKED,
        revocation_time=rev_naive,
    )
    # Remove revocation_time_utc completely (constructor doesn't set it).
    with pytest.raises(RevokedCertificateException) as exc_info:
        helper.verify_resp_status(resp)  # type: ignore[arg-type]
    assert exc_info.value.get_revocation_time() == rev_naive


# ---------------------------------------------------------------------------
# nonce roundtrip
# ---------------------------------------------------------------------------


def test_build_ocsp_request_nonce_matches_get_nonce(self_signed_cert) -> None:
    """``build_ocsp_request`` stores the generated nonce so callers can
    confirm it via ``get_nonce`` afterwards."""
    helper = _helper(self_signed_cert)
    assert helper.get_nonce() is None
    helper.build_ocsp_request()
    nonce = helper.get_nonce()
    assert isinstance(nonce, bytes)
    assert len(nonce) == 16


def test_build_ocsp_request_handles_import_error(
    monkeypatch, self_signed_cert,
) -> None:
    """When ``OCSPNonce`` can't be imported (very old ``cryptography``),
    the helper drops the nonce silently rather than crashing — exercises
    the ``except ImportError`` arm of :meth:`build_ocsp_request`."""
    real_import = importlib.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        # Block any attempt to import OCSPNonce from cryptography.x509.
        if (
            name == "cryptography.x509"
            and fromlist
            and "OCSPNonce" in fromlist
        ):
            raise ImportError("simulated missing OCSPNonce")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _fake_import)
    helper = _helper(self_signed_cert)
    der = helper.build_ocsp_request()
    assert isinstance(der, bytes) and len(der) > 0
    # The except branch clears the nonce so callers know to fall back.
    assert helper.get_nonce() is None


# ---------------------------------------------------------------------------
# accessor coverage
# ---------------------------------------------------------------------------


def test_accessors_round_trip_inputs(self_signed_cert) -> None:
    cert, _ = self_signed_cert
    sign_date = _dt.datetime(2025, 1, 1, tzinfo=_dt.UTC)
    helper = OcspHelper(
        cert_to_check=cert,
        sign_date=sign_date,
        issuer_certificate=cert,
        additional_certs=[],
        ocsp_url="http://ocsp.example/path",
    )
    assert helper.get_certificate_to_check() is cert
    assert helper.get_issuer_certificate() is cert
    assert helper.get_ocsp_url() == "http://ocsp.example/path"
    assert helper.get_response_ocsp() is None
    assert helper.get_basic_ocsp_resp() is None


def test_get_basic_ocsp_resp_mirrors_get_response_ocsp(self_signed_cert) -> None:
    """``get_basic_ocsp_resp`` is a synonym for ``get_response_ocsp`` in the
    pypdfbox port — both should return the captured response."""
    helper = _helper(self_signed_cert)
    resp = _StubOcspResponse()
    helper.verify_resp_status(resp)  # type: ignore[arg-type]
    assert helper.get_response_ocsp() is resp
    assert helper.get_basic_ocsp_resp() is resp


def test_verify_ocsp_response_delegates_to_verify_resp_status(
    self_signed_cert,
) -> None:
    """:meth:`verify_ocsp_response` is the upstream public alias of
    :meth:`verify_resp_status`."""
    helper = _helper(self_signed_cert)
    resp = _StubOcspResponse()
    helper.verify_ocsp_response(resp)  # type: ignore[arg-type]
    assert helper.get_response_ocsp() is resp


# ---------------------------------------------------------------------------
# negative branches — error wrapping
# ---------------------------------------------------------------------------


def test_verify_resp_status_unknown_raises_ocsp_exception(self_signed_cert) -> None:
    """An ``UNKNOWN`` certificate status produces an :class:`OcspException`
    (not a :class:`RevokedCertificateException`)."""
    helper = _helper(self_signed_cert)
    resp = _StubOcspResponse(certificate_status=ocsp.OCSPCertStatus.UNKNOWN)
    with pytest.raises(OcspException, match="UNKNOWN"):
        helper.verify_resp_status(resp)  # type: ignore[arg-type]


def test_generate_ocsp_request_returns_der_bytes(self_signed_cert) -> None:
    """The public ``generate_ocsp_request`` thin-wrapper still produces
    a valid DER blob (parsable by ``cryptography.x509.ocsp``)."""
    helper = _helper(self_signed_cert)
    der = helper.generate_ocsp_request()
    # Cryptography parses the DER back into an OCSPRequest object.
    parsed = ocsp.load_der_ocsp_request(der)
    assert parsed is not None


def test_check_ocsp_signature_without_response_raises(self_signed_cert) -> None:
    """Calling :meth:`check_ocsp_signature` before any response is
    captured surfaces the explicit "No OCSP response captured" guard."""
    helper = _helper(self_signed_cert)
    cert, _ = self_signed_cert
    with pytest.raises(OcspException, match="No OCSP response captured"):
        helper.check_ocsp_signature(cert)

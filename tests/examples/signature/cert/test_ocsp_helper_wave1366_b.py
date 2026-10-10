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

import datetime as _dt
import importlib

import pytest
from cryptography import x509
from cryptography.x509 import ocsp

from pypdfbox.examples.signature.cert.ocsp_helper import (
    OcspException,
    OcspHelper,
    _single_attr,
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


def test_single_attr_prefers_revocation_time_utc() -> None:
    """When a single response exposes both ``revocation_time_utc`` and
    ``revocation_time``, the timezone-aware variant wins."""
    rev_utc = _dt.datetime(2024, 1, 2, tzinfo=_dt.UTC)
    rev_naive = _dt.datetime(2023, 6, 15)
    resp = _StubOcspResponse(
        certificate_status=ocsp.OCSPCertStatus.REVOKED,
        revocation_time=rev_naive,
        revocation_time_utc=rev_utc,
    )
    assert _single_attr(resp, "revocation_time") == rev_utc


def test_single_attr_falls_back_to_revocation_time() -> None:
    """If ``revocation_time_utc`` is absent, fall back to the naive one."""
    rev_naive = _dt.datetime(2022, 3, 1)
    resp = _StubOcspResponse(
        certificate_status=ocsp.OCSPCertStatus.REVOKED,
        revocation_time=rev_naive,
    )
    assert _single_attr(resp, "revocation_time") == rev_naive


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
    assert helper.get_basic_ocsp_resp() is None


def test_verify_resp_status_does_not_capture_response(self_signed_cert) -> None:
    """Only a fully verified response is captured; the status check alone
    (upstream ``verifyRespStatus``) does not store anything."""
    helper = _helper(self_signed_cert)
    resp = _StubOcspResponse()
    helper.verify_resp_status(resp)  # type: ignore[arg-type]
    assert helper.get_basic_ocsp_resp() is None


def test_verify_ocsp_response_checks_status_first(self_signed_cert) -> None:
    """:meth:`verify_ocsp_response` starts with :meth:`verify_resp_status`."""
    helper = _helper(self_signed_cert)
    resp = _StubOcspResponse(response_status=ocsp.OCSPResponseStatus.TRY_LATER)
    with pytest.raises(OcspException, match="TRY_LATER"):
        helper.verify_ocsp_response(resp)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# negative branches — error wrapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "label"),
    [
        (ocsp.OCSPResponseStatus.INTERNAL_ERROR, "INTERNAL_ERROR"),
        (ocsp.OCSPResponseStatus.MALFORMED_REQUEST, "MALFORMED_REQUEST"),
        (ocsp.OCSPResponseStatus.SIG_REQUIRED, "SIG_REQUIRED"),
        (ocsp.OCSPResponseStatus.TRY_LATER, "TRY_LATER"),
        (ocsp.OCSPResponseStatus.UNAUTHORIZED, "UNAUTHORIZED"),
    ],
)
def test_verify_resp_status_unsuccessful_labels(self_signed_cert, status, label) -> None:
    helper = _helper(self_signed_cert)
    resp = _StubOcspResponse(response_status=status)
    with pytest.raises(OcspException, match=f"unsuccessful, status: {label}"):
        helper.verify_resp_status(resp)  # type: ignore[arg-type]


def test_verify_resp_status_none_raises(self_signed_cert) -> None:
    helper = _helper(self_signed_cert)
    with pytest.raises(OcspException, match="unsuccessful"):
        helper.verify_resp_status(None)


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

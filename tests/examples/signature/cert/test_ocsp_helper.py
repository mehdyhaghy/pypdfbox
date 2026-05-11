"""Tests for ``OcspHelper``."""

from __future__ import annotations

import pytest

from pypdfbox.examples.signature.cert.ocsp_helper import OcspException, OcspHelper


def test_constructor_stores_inputs(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    helper = OcspHelper(
        cert_to_check=cert,
        sign_date=None,
        issuer_certificate=cert,
        additional_certs=[],
        ocsp_url="http://ocsp.test.invalid/check",
    )
    assert helper.get_ocsp_url() == "http://ocsp.test.invalid/check"
    assert helper.get_response_ocsp() is None


def test_build_ocsp_request_returns_non_empty_der(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    helper = OcspHelper(cert, None, cert, [], "http://ocsp.test.invalid")
    blob = helper.build_ocsp_request()
    assert isinstance(blob, bytes)
    assert blob.startswith(b"\x30")  # SEQUENCE tag


def test_ocsp_exception_is_exception():
    with pytest.raises(OcspException):
        raise OcspException("bad")

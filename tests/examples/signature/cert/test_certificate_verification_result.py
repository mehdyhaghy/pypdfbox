"""Tests for ``CertificateVerificationResult``."""

from __future__ import annotations

from pypdfbox.examples.signature.cert.certificate_verification_result import (
    CertificateVerificationResult,
)


def test_valid_result_carries_payload():
    payload = ["leaf", "root"]
    result = CertificateVerificationResult(result=payload)
    assert result.is_valid() is True
    assert result.get_result() == payload
    assert result.get_exception() is None


def test_failure_carries_exception():
    err = ValueError("nope")
    result = CertificateVerificationResult(exception=err)
    assert result.is_valid() is False
    assert result.get_result() is None
    assert result.get_exception() is err

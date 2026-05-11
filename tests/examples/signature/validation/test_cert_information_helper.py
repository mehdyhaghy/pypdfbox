"""Tests for ``CertInformationHelper``."""

from __future__ import annotations

import hashlib

import pytest

from pypdfbox.examples.signature.validation.cert_information_helper import (
    CertInformationHelper,
)
from pypdfbox.examples.signature.validation.cert_signature_information import (
    CertSignatureInformation,
)


def test_static_helper_cannot_be_instantiated():
    with pytest.raises(RuntimeError):
        CertInformationHelper()


def test_get_sha1_hash_returns_uppercase_hex():
    expected = hashlib.sha1(b"abc", usedforsecurity=False).hexdigest().upper()
    assert CertInformationHelper.get_sha1_hash(b"abc") == expected


def test_authority_info_extension_populates_urls(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    info = CertSignatureInformation()
    CertInformationHelper.get_authority_info_extension_value(cert, info)
    assert info.get_ocsp_url() == "http://ocsp.test.invalid/check"
    assert info.get_issuer_url() == "http://ca.test.invalid/issuer.crt"


def test_crl_url_from_extension_value(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    assert (
        CertInformationHelper.get_crl_url_from_extension_value(cert)
        == "http://crl.test.invalid/list.crl"
    )


def test_no_aia_returns_none(self_signed_cert):
    cert, _ = self_signed_cert
    info = CertSignatureInformation()
    CertInformationHelper.get_authority_info_extension_value(cert, info)
    assert info.get_ocsp_url() is None
    assert info.get_issuer_url() is None


def test_no_crl_returns_none(self_signed_cert):
    cert, _ = self_signed_cert
    assert CertInformationHelper.get_crl_url_from_extension_value(cert) is None

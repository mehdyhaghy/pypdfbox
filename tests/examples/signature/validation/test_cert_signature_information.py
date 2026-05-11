"""Tests for ``CertSignatureInformation``."""

from __future__ import annotations

from pypdfbox.examples.signature.validation.cert_signature_information import (
    CertSignatureInformation,
)


def test_default_values_are_empty():
    info = CertSignatureInformation()
    assert info.get_certificate() is None
    assert info.get_signature_hash() is None
    assert info.is_self_signed() is False
    assert info.get_ocsp_url() is None
    assert info.get_crl_url() is None
    assert info.get_issuer_url() is None
    assert info.get_issuer_certificates() == set()
    assert info.get_cert_chain() is None
    assert info.get_tsa_certs() is None
    assert info.get_alternative_cert_chain() is None


def test_setters_round_trip():
    info = CertSignatureInformation()
    info.set_certificate("cert")
    info.set_signature_hash("ABCD")
    info.set_self_signed(True)
    info.set_ocsp_url("http://o")
    info.set_crl_url("http://c")
    info.set_issuer_url("http://i")
    child = CertSignatureInformation()
    info.set_cert_chain(child)
    info.set_tsa_certs(child)
    info.set_alternative_cert_chain(child)
    assert info.get_certificate() == "cert"
    assert info.get_signature_hash() == "ABCD"
    assert info.is_self_signed() is True
    assert info.get_ocsp_url() == "http://o"
    assert info.get_crl_url() == "http://c"
    assert info.get_issuer_url() == "http://i"
    assert info.get_cert_chain() is child
    assert info.get_tsa_certs() is child
    assert info.get_alternative_cert_chain() is child

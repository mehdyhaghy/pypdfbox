"""Tests for ``CreateSignature``."""

from __future__ import annotations

from pypdfbox.examples.signature.create_signature import CreateSignature


def test_create_signature_extends_base(pkcs12_bytes, tsa_password):
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    assert signer.get_certificate_chain()


def test_has_sign_detached_methods(pkcs12_bytes, tsa_password):
    signer = CreateSignature(pkcs12_bytes, tsa_password)
    assert callable(signer.sign_detached)
    assert callable(signer.sign_detached_document)

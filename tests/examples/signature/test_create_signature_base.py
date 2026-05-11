"""Tests for ``CreateSignatureBase``."""

from __future__ import annotations

from io import BytesIO

import pytest
from cryptography.hazmat.primitives.serialization import pkcs7

from pypdfbox.examples.signature.create_signature_base import CreateSignatureBase


def test_loads_pkcs12_keystore(pkcs12_bytes, tsa_password):
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    chain = signer.get_certificate_chain()
    assert len(chain) >= 1


def test_external_signing_flag_round_trips(pkcs12_bytes, tsa_password):
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    assert signer.is_external_signing() is False
    signer.set_external_signing(True)
    assert signer.is_external_signing() is True


def test_sign_returns_detached_pkcs7(pkcs12_bytes, tsa_password):
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    payload = b"document content"
    blob = signer.sign(BytesIO(payload))
    assert isinstance(blob, bytes) and len(blob) > 0
    # PKCS#7 contents should at least carry the signing certificate.
    certs = pkcs7.load_der_pkcs7_certificates(blob)
    assert len(certs) >= 1


def test_constructor_raises_with_bad_password(pkcs12_bytes):
    # cryptography raises ValueError when the PKCS#12 password is wrong.
    with pytest.raises(ValueError):
        CreateSignatureBase(pkcs12_bytes, b"wrong-pin")

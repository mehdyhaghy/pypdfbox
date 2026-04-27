"""Hand-written coverage for :class:`PublicKeyDecryptionMaterial`.

Exercises the certificate / private-key / password slots — including the
lazy PEM/DER decode paths — without touching the security handler.
"""

from __future__ import annotations

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel.encryption import PublicKeyDecryptionMaterial


def _build_self_signed() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    """Mint a tiny self-signed RSA cert for the round-trip tests."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-test")]
    )
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return key, cert


def test_default_state() -> None:
    material = PublicKeyDecryptionMaterial()
    assert material.get_certificate() is None
    assert material.get_private_key() is None
    assert material.get_password() is None


def test_password_round_trip() -> None:
    material = PublicKeyDecryptionMaterial(password=b"hunter2")
    assert material.get_password() == b"hunter2"
    material.set_password(None)
    assert material.get_password() is None


def test_set_certificate_accepts_certificate_object() -> None:
    _, cert = _build_self_signed()
    material = PublicKeyDecryptionMaterial(certificate=cert)
    assert material.get_certificate() is cert


def test_set_certificate_decodes_pem_bytes() -> None:
    _, cert = _build_self_signed()
    pem = cert.public_bytes(serialization.Encoding.PEM)
    material = PublicKeyDecryptionMaterial(certificate=pem)
    loaded = material.get_certificate()
    assert loaded is not None
    assert loaded.subject == cert.subject


def test_set_certificate_decodes_der_bytes() -> None:
    _, cert = _build_self_signed()
    der = cert.public_bytes(serialization.Encoding.DER)
    material = PublicKeyDecryptionMaterial(certificate=der)
    loaded = material.get_certificate()
    assert loaded is not None
    assert loaded.subject == cert.subject


def test_set_certificate_rejects_unknown_type() -> None:
    material = PublicKeyDecryptionMaterial()
    with pytest.raises(TypeError, match="unsupported certificate type"):
        material.set_certificate(12345)  # type: ignore[arg-type]


def test_private_key_round_trip_with_object() -> None:
    key, _ = _build_self_signed()
    material = PublicKeyDecryptionMaterial(private_key=key)
    assert material.get_private_key() is key


def test_private_key_lazy_pem_decode() -> None:
    key, _ = _build_self_signed()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    material = PublicKeyDecryptionMaterial(private_key=pem)
    decoded = material.get_private_key()
    assert decoded is not None
    # Private number must round-trip — proves we got the same key back.
    assert decoded.private_numbers().d == key.private_numbers().d  # type: ignore[union-attr]


def test_private_key_lazy_der_decode_with_password() -> None:
    key, _ = _build_self_signed()
    password = b"correct horse battery staple"
    der = key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )
    material = PublicKeyDecryptionMaterial(private_key=der, password=password)
    decoded = material.get_private_key()
    assert decoded is not None
    assert decoded.private_numbers().d == key.private_numbers().d  # type: ignore[union-attr]

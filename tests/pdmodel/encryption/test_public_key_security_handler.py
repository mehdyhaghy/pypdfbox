from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.public_key_decryption_material import (
    PublicKeyDecryptionMaterial,
)
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import PublicKeyRecipient
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)


def test_protection_policy_collects_recipients() -> None:
    policy = PublicKeyProtectionPolicy()
    r1 = PublicKeyRecipient()
    r2 = PublicKeyRecipient()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    assert policy.get_recipients() == [r1, r2]
    assert policy.get_number_of_recipients() == 2


def test_protection_policy_remove_recipient_returns_bool() -> None:
    policy = PublicKeyProtectionPolicy()
    r = PublicKeyRecipient()
    policy.add_recipient(r)
    assert policy.remove_recipient(r) is True
    assert policy.remove_recipient(r) is False
    assert policy.get_recipients() == []


def test_recipient_round_trips_cert_and_permission() -> None:
    perm = AccessPermission()
    perm.set_can_print(False)
    sentinel_cert = object()  # stand-in — type only enforced statically
    r = PublicKeyRecipient(certificate=sentinel_cert, permissions=perm)  # type: ignore[arg-type]
    assert r.get_x509() is sentinel_cert
    assert r.get_permission() is perm
    other_perm = AccessPermission.get_owner_access_permission()
    r.set_permission(other_perm)
    assert r.get_permission() is other_perm
    r.set_x509(None)
    assert r.get_x509() is None


def test_decryption_material_round_trips_cert_and_key() -> None:
    sentinel_cert = object()
    sentinel_key = object()
    material = PublicKeyDecryptionMaterial(password=b"hunter2")
    # Use the bypass setters with sentinels — set_certificate validates type,
    # so we set the underlying field directly to avoid touching real PEM/DER
    # material in this unit test.
    material._certificate = sentinel_cert  # type: ignore[assignment]
    material.set_private_key(sentinel_key)  # type: ignore[arg-type]
    assert material.get_certificate() is sentinel_cert
    # Already-loaded keys (non-bytes) are returned as-is.
    assert material.get_private_key() is sentinel_key
    assert material.get_password() == b"hunter2"
    material.set_password(None)
    assert material.get_password() is None


def test_decryption_material_rejects_unknown_certificate_type() -> None:
    material = PublicKeyDecryptionMaterial()
    with pytest.raises(TypeError):
        material.set_certificate(12345)  # type: ignore[arg-type]


def test_security_handler_filter_constant() -> None:
    assert PublicKeySecurityHandler.FILTER == "Adobe.PubSec"


def test_prepare_document_requires_recipients() -> None:
    handler = PublicKeySecurityHandler(PublicKeyProtectionPolicy())
    with pytest.raises(ValueError, match="recipient"):
        handler.prepare_document(object())


def test_prepare_document_requires_protection_policy() -> None:
    handler = PublicKeySecurityHandler()
    with pytest.raises(ValueError, match="PublicKeyProtectionPolicy"):
        handler.prepare_document(object())


def test_prepare_for_decryption_rejects_wrong_material_type() -> None:
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

    handler = PublicKeySecurityHandler()
    with pytest.raises(TypeError):
        handler.prepare_for_decryption(PDEncryption(), b"id", object())


def test_prepare_for_decryption_requires_recipient_array() -> None:
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

    handler = PublicKeySecurityHandler()
    material = PublicKeyDecryptionMaterial()
    # Inject sentinels so the cert/key None check passes and we exercise the
    # /Recipients lookup branch instead.
    material._certificate = object()  # type: ignore[assignment]
    material._private_key_raw = object()  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Recipients"):
        handler.prepare_for_decryption(PDEncryption(), b"id", material)


def _build_self_signed_rsa() -> tuple[object, object]:
    """Return ``(cert, private_key)`` — a fresh self-signed 2048-bit RSA
    certificate suitable for one-shot CMS recipient wrapping."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-test-recipient")]
    )
    not_before = datetime.datetime(2020, 1, 1)
    not_after = datetime.datetime(2040, 1, 1)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(private_key, hashes.SHA256())
    )
    return cert, private_key


class _StubDocument:
    """Minimal stand-in for PDDocument.set_encryption_dictionary capture.

    The handler only needs ``set_encryption_dictionary`` to be callable; we
    re-use the captured PDEncryption on the decrypt side instead of round-
    tripping through a real COSDocument trailer.
    """

    def __init__(self) -> None:
        self.encryption = None

    def set_encryption_dictionary(self, encryption: object) -> None:
        self.encryption = encryption


@pytest.mark.parametrize("key_length_bits", [128, 256])
def test_prepare_document_round_trip_matches_decrypt_path(
    key_length_bits: int,
) -> None:
    """Encrypt a synthetic document, decrypt it, assert keys agree.

    This is the public-key analogue of the standard-handler round-trip — we
    don't write a full PDF, just verify that ``prepare_document`` produces a
    `/Recipients`/`/CF` set that ``prepare_for_decryption`` can consume back
    into the *same* file-encryption key.
    """
    try:
        cert, private_key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    permissions = AccessPermission()
    permissions.set_can_print(False)
    recipient = PublicKeyRecipient(certificate=cert, permissions=permissions)

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(recipient)
    policy.set_encryption_key_length(key_length_bits)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)

    assert document.encryption is not None
    assert document.encryption.get_filter() == "Adobe.PubSec"
    assert document.encryption.get_length() == key_length_bits
    if key_length_bits == 256:
        assert document.encryption.get_v() == 5
        assert document.encryption.get_sub_filter() == "adbe.pkcs7.s5"
    else:
        assert document.encryption.get_v() == 4
        assert document.encryption.get_sub_filter() == "adbe.pkcs7.s4"
    recipients_array = document.encryption.get_recipients()
    assert recipients_array is not None
    assert recipients_array.size() == 1

    encrypt_key = handler.get_encryption_key()
    assert encrypt_key is not None
    assert len(encrypt_key) == key_length_bits // 8

    # Decrypt path — feed the same /Encrypt back through with the matching
    # private key and verify the derived file-encryption key matches.
    material = PublicKeyDecryptionMaterial(certificate=cert, private_key=private_key)
    decrypt_handler = PublicKeySecurityHandler()
    decrypt_handler.prepare_for_decryption(
        document.encryption, b"\x00" * 16, material
    )
    assert decrypt_handler.get_encryption_key() == encrypt_key
    assert decrypt_handler.get_key_length() == key_length_bits
    assert decrypt_handler.is_aes() is True

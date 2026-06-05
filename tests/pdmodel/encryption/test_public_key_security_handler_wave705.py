from __future__ import annotations

import hashlib

import pytest

import pypdfbox.pdmodel.encryption.pd_encryption as pd_encryption_module
import pypdfbox.pdmodel.encryption.public_key_security_handler as pksh_module
from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
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


def _material_with_sentinels() -> PublicKeyDecryptionMaterial:
    material = PublicKeyDecryptionMaterial()
    material._certificate = object()  # type: ignore[assignment]
    material._private_key_raw = object()  # type: ignore[assignment]
    return material


def test_prepare_for_decryption_requires_certificate_and_private_key() -> None:
    with pytest.raises(ValueError, match="certificate or private key"):
        PublicKeySecurityHandler().prepare_for_decryption(
            PDEncryption(), b"document-id", PublicKeyDecryptionMaterial()
        )


def test_prepare_for_decryption_rejects_non_string_recipient_entry() -> None:
    encryption = PDEncryption()
    recipients = COSArray([COSInteger.get(1)])
    encryption.get_cos_object().set_item(COSName.get_pdf_name("Recipients"), recipients)

    with pytest.raises(ValueError, match=r"/Recipients\[0\] is not a COSString"):
        PublicKeySecurityHandler().prepare_for_decryption(
            encryption, b"document-id", _material_with_sentinels()
        )


def test_prepare_for_decryption_rejects_short_decrypted_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encryption = PDEncryption()
    encryption.set_recipients([b"recipient-envelope"])

    monkeypatch.setattr(
        pksh_module.pkcs7,
        "pkcs7_decrypt_der",
        lambda *_args, **_kwargs: b"too-short",
    )

    with pytest.raises(ValueError, match="shorter than the 20-byte seed"):
        PublicKeySecurityHandler().prepare_for_decryption(
            encryption, b"document-id", _material_with_sentinels()
        )


def test_prepare_for_decryption_derives_key_with_metadata_sentinel_and_positive_perms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = b"s" * 20
    recipient_blob = b"recipient-envelope"
    encryption = PDEncryption()
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_length(128)
    encryption.set_encrypt_meta_data(False)
    encryption.set_recipients([recipient_blob])

    monkeypatch.setattr(
        pksh_module.pkcs7,
        "pkcs7_decrypt_der",
        lambda *_args, **_kwargs: seed + (4).to_bytes(4, "big"),
    )

    handler = PublicKeySecurityHandler()
    handler.prepare_for_decryption(
        encryption, b"document-id", _material_with_sentinels()
    )

    expected = hashlib.sha1(  # noqa: S324 - mirrors PDF public-key algorithm
        seed + recipient_blob + b"\xff\xff\xff\xff",
        usedforsecurity=False,
    ).digest()[:16]
    assert handler.get_encryption_key() == expected
    assert handler.get_current_access_permission() is not None
    assert handler.get_current_access_permission().get_permission_bytes() == 4


def test_prepare_document_requires_recipient_certificate() -> None:
    recipient = PublicKeyRecipient(permissions=AccessPermission())
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(recipient)

    with pytest.raises(ValueError, match="X.509 certificate"):
        PublicKeySecurityHandler(policy).prepare_document(object())


def test_prepare_document_requires_recipient_permissions() -> None:
    recipient = PublicKeyRecipient(certificate=object())  # type: ignore[arg-type]
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(recipient)

    with pytest.raises(ValueError, match="AccessPermission"):
        PublicKeySecurityHandler(policy).prepare_document(object())


def test_prepare_document_metadata_false_sentinel_participates_in_key_derivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MetadataFalseEncryption(PDEncryption):
        def is_encrypt_meta_data(self) -> bool:
            return False

    class FakeEnvelopeBuilder:
        def set_data(self, data: bytes) -> FakeEnvelopeBuilder:
            # Upstream packs getPermissionBytesForPublicKey() (bit 1 set,
            # bits 7/8 + 13-32 cleared), NOT the raw getPermissionBytes().
            assert data == (b"s" * 20) + AccessPermission()\
                .get_permission_bytes_for_public_key().to_bytes(4, "big", signed=True)
            return self

        def add_recipient(self, _cert: object) -> FakeEnvelopeBuilder:
            return self

        def set_content_encryption_algorithm(
            self, _algorithm: object
        ) -> FakeEnvelopeBuilder:
            return self

        def encrypt(self, *_args: object, **_kwargs: object) -> bytes:
            return b"envelope-der"

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(
        PublicKeyRecipient(
            certificate=object(),  # type: ignore[arg-type]
            permissions=AccessPermission(),
        )
    )
    policy.set_encryption_key_length(128)

    monkeypatch.setattr(pksh_module.os, "urandom", lambda _n: b"s" * 20)
    monkeypatch.setattr(
        pksh_module.pkcs7, "PKCS7EnvelopeBuilder", FakeEnvelopeBuilder
    )
    monkeypatch.setattr(pd_encryption_module, "PDEncryption", MetadataFalseEncryption)

    handler = PublicKeySecurityHandler(policy)
    handler.prepare_document(object())

    expected = hashlib.sha1(  # noqa: S324 - mirrors PDF public-key algorithm
        (b"s" * 20) + b"envelope-der" + b"\xff\xff\xff\xff",
        usedforsecurity=False,
    ).digest()[:16]
    assert handler.get_encryption_key() == expected


def test_coerce_recipients_accepts_only_cos_array() -> None:
    recipients = COSArray()

    assert PublicKeySecurityHandler._coerce_recipients(recipients) is recipients
    assert PublicKeySecurityHandler._coerce_recipients(object()) is None

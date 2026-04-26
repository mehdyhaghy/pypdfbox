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


def test_prepare_document_is_deferred() -> None:
    handler = PublicKeySecurityHandler()
    with pytest.raises(NotImplementedError):
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


@pytest.mark.skip(reason="needs cert fixture (real X.509 + private key + encrypted PDF)")
def test_prepare_for_decryption_round_trip() -> None:
    # Wiring this test requires a CMS-enveloped recipient blob plus the
    # matching X.509 certificate and private key. Defer until we have the
    # public-key fixture corpus from upstream PDFBox.
    raise AssertionError("unreachable — skipped above")

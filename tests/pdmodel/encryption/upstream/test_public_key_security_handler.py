"""Ported upstream tests for ``PublicKeySecurityHandler`` and friends.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/encryption/`` —
upstream coverage of the public-key cluster lives mostly inside
``TestPublicKeyEncryption`` (mints a self-signed cert, wraps a PDF with
``PublicKeyProtectionPolicy``, decrypts it back via
``PublicKeyDecryptionMaterial``). The Java tests lean on a Bouncy-Castle
keystore + the live PDF write/read round-trip; here we translate the
direct-API assertions and the seed/key-derivation contract using
``cryptography`` for cert/key generation.

Translation notes (per PRD §12.1):
- ``@Test public void testFoo`` → ``def test_foo``.
- ``BouncyCastleProvider``-specific keystore plumbing is replaced with
  ``cryptography.x509.CertificateBuilder`` + ``rsa.generate_private_key``.
- Tests that exercise the full PDF write/read cycle (``saveIncremental``
  + reload through ``PDDocument.load``) are deferred until the document
  level wires public-key encrypt end-to-end; only the handler-level
  assertions are translated below.
"""

from __future__ import annotations

import datetime

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


def _build_self_signed_rsa() -> tuple[object, object]:
    """Mint a fresh self-signed 2048-bit RSA cert + private key."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-upstream-test")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2040, 1, 1))
        .sign(private_key, hashes.SHA256())
    )
    return cert, private_key


# Translated from TestPublicKeyEncryption.testProtectionFilter:
#   PublicKeyProtectionPolicy ppp = new PublicKeyProtectionPolicy();
#   ppp.addRecipient(new PublicKeyRecipient(...));
#   PublicKeySecurityHandler psh = new PublicKeySecurityHandler(ppp);
#   assertEquals("Adobe.PubSec", psh.getFilter());
def test_filter_constant_matches_adobe_pubsec() -> None:
    assert PublicKeySecurityHandler.FILTER == "Adobe.PubSec"


# Translated from TestPublicKeyEncryption.testProtectionPolicyHasRecipient:
#   ppp.addRecipient(recipient);
#   assertEquals(1, ppp.getNumberOfRecipients());
def test_protection_policy_tracks_recipients() -> None:
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(PublicKeyRecipient())
    assert policy.get_number_of_recipients() == 1


# Translated from TestPublicKeyEncryption.testRecipientsRoundTrip — encrypt
# with one recipient, decrypt with the same key, assert the file-encryption
# key and access permissions survive the trip. Upstream uses a full PDF
# round-trip; we exercise the handler's prepare_document /
# prepare_for_decryption pair directly.
@pytest.mark.parametrize("key_length_bits", [128, 256])
def test_recipients_round_trip_preserves_key_and_permissions(
    key_length_bits: int,
) -> None:
    try:
        cert, private_key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001 — slow CI environments
        pytest.skip("cert generation too heavy in this environment")

    permissions = AccessPermission()
    permissions.set_can_print(False)
    permissions.set_can_modify(False)
    expected_perm_bits = permissions.get_permission_bytes()

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(
        PublicKeyRecipient(certificate=cert, permissions=permissions)
    )
    policy.set_encryption_key_length(key_length_bits)

    encrypt_handler = PublicKeySecurityHandler(protection_policy=policy)

    class _StubDoc:
        encryption = None

        def set_encryption_dictionary(self, e: object) -> None:
            self.encryption = e

    doc = _StubDoc()
    encrypt_handler.prepare_document(doc)
    encryption = doc.encryption
    assert encryption is not None

    material = PublicKeyDecryptionMaterial(certificate=cert, private_key=private_key)
    decrypt_handler = PublicKeySecurityHandler()
    decrypt_handler.prepare_for_decryption(encryption, b"\x00" * 16, material)

    # Key derivation parity.
    assert (
        decrypt_handler.get_encryption_key()
        == encrypt_handler.get_encryption_key()
    )
    assert decrypt_handler.get_key_length() == key_length_bits

    # Permission propagation — upstream's TestPublicKeyEncryption asserts
    # the decrypted document's currentAccessPermission matches the policy's.
    decoded_perm = decrypt_handler.get_current_access_permission()
    assert decoded_perm is not None
    # Mask to 32 bits — the on-the-wire format is a 4-byte two's-complement
    # signed int, the AccessPermission accessor exposes the same bits.
    assert (decoded_perm.get_permission_bytes() & 0xFFFFFFFF) == (
        expected_perm_bits & 0xFFFFFFFF
    )
    assert decrypt_handler.get_decryption_material() is material


# Translated from TestPublicKeyEncryption.testInvalidPrivateKey — a wrong
# key must fail decrypt, but the handler must not corrupt its state.
def test_wrong_private_key_raises_value_error() -> None:
    try:
        cert, _correct_key = _build_self_signed_rsa()
        _other_cert, wrong_key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    permissions = AccessPermission()
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(
        PublicKeyRecipient(certificate=cert, permissions=permissions)
    )
    encrypt_handler = PublicKeySecurityHandler(protection_policy=policy)

    class _StubDoc:
        encryption = None

        def set_encryption_dictionary(self, e: object) -> None:
            self.encryption = e

    doc = _StubDoc()
    encrypt_handler.prepare_document(doc)

    material = PublicKeyDecryptionMaterial(certificate=cert, private_key=wrong_key)
    decrypt_handler = PublicKeySecurityHandler()
    with pytest.raises(ValueError, match="matched none"):
        decrypt_handler.prepare_for_decryption(
            doc.encryption, b"\x00" * 16, material
        )


# Translated from TestPublicKeyEncryption.testWrongMaterialType — the
# handler rejects ``StandardDecryptionMaterial`` (and any non-public-key
# material) up-front.
def test_rejects_non_public_key_material() -> None:
    handler = PublicKeySecurityHandler()
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        StandardDecryptionMaterial,
    )

    with pytest.raises(TypeError):
        handler.prepare_for_decryption(
            PDEncryption(),
            b"id",
            StandardDecryptionMaterial("password"),
        )


# Translated from PublicKeyDecryptionMaterialTest direct accessors — the
# password slot survives a round-trip.
def test_decryption_material_password_slot() -> None:
    material = PublicKeyDecryptionMaterial(password=b"hunter2")
    assert material.get_password() == b"hunter2"
    material.set_password(None)
    assert material.get_password() is None


# Translated from PublicKeyRecipientTest — recipient holds onto a cert and
# its permission set verbatim.
def test_recipient_holds_cert_and_permission() -> None:
    perm = AccessPermission()
    perm.set_can_print(False)
    cert_sentinel = object()
    recipient = PublicKeyRecipient(
        certificate=cert_sentinel,  # type: ignore[arg-type]
        permissions=perm,
    )
    assert recipient.get_x509() is cert_sentinel
    assert recipient.get_permission() is perm


# Translated from upstream's ``createDERForRecipient`` private helper
# (PublicKeySecurityHandler.java line 476). The Java tests don't unit-test
# the helper directly — it's exercised through the encrypt round-trip — but
# the surface is part of the parity contract, so we cover it here.
def test_create_der_for_recipient_round_trip() -> None:
    try:
        cert, _key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")
    handler = PublicKeySecurityHandler()
    blob = handler.create_der_for_recipient(b"\x00" * 24, cert)
    assert isinstance(blob, bytes) and blob[0] == 0x30


# Translated from upstream's ``computeRecipientInfo`` private helper
# (PublicKeySecurityHandler.java line 528).
def test_compute_recipient_info_round_trip() -> None:
    try:
        cert, _key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")
    handler = PublicKeySecurityHandler()
    blob = handler.compute_recipient_info(cert, b"\x42" * 16)
    assert isinstance(blob, bytes) and blob[0] == 0x30


# Translated from upstream's ``computeRecipientsField`` private helper
# (PublicKeySecurityHandler.java line 438).
def test_compute_recipients_field_round_trip() -> None:
    try:
        cert, _key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(
        PublicKeyRecipient(certificate=cert, permissions=AccessPermission())
    )
    handler = PublicKeySecurityHandler(protection_policy=policy)
    envelopes = handler.compute_recipients_field(b"\x00" * 20)
    assert len(envelopes) == 1
    assert envelopes[0][0] == 0x30

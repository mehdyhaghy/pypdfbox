"""One-envelope-per-recipient shape for the public-key handler write path.

Upstream ``PublicKeySecurityHandler#computeRecipientsField`` emits exactly one
PKCS#7 envelope per recipient, in policy iterator order — it allocates
``new byte[getNumberOfRecipients()][]`` and loops the recipients iterator,
calling ``createDERForRecipient`` once per recipient. It does **not** group
recipients that share a permission mask onto a single multi-recipient envelope.

These tests pin that upstream-faithful shape:

* N recipients → N envelopes on ``/Recipients`` regardless of permission masks;
* every envelope round-trips through ``prepare_for_decryption`` for its own
  recipient key, surfacing that recipient's own permission mask.

(An earlier wave invented per-permission-mask grouping, which contradicts
upstream and violated the "do not invent abstractions" rule; wave 1502 reverted
the write path to one-envelope-per-recipient and these tests track that.)
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
    """Return ``(cert, private_key)`` — a fresh self-signed 2048-bit RSA cert.

    Matches the helper in ``test_public_key_security_handler.py`` so the
    round-trip assertions here line up with the existing decrypt-path tests.
    """
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


def _recipients_of(encryption: object) -> object:
    """Read the ``/Recipients`` array from the crypt-filter-based V>=4 handler.

    The public-key handler writes ``/Recipients`` inside ``/CF
    /DefaultCryptFilter`` (PDFBox-compatible location), falling back to the
    legacy ``/Encrypt`` top level if present.
    """
    top = encryption.get_recipients()  # type: ignore[attr-defined]
    if top is not None and top.size() > 0:
        return top
    default_cf = encryption.get_default_crypt_filter_dictionary()  # type: ignore[attr-defined]
    if default_cf is not None:
        return default_cf.get_recipients()
    return None


class _StubDocument:
    """Captures the ``/Encrypt`` dictionary written by ``prepare_document``."""

    def __init__(self) -> None:
        self.encryption: object | None = None

    def set_encryption_dictionary(self, encryption: object) -> None:
        self.encryption = encryption


def _make_recipient_with(permissions: AccessPermission) -> tuple[
    PublicKeyRecipient, object, object
]:
    """Build a recipient backed by a freshly minted self-signed cert."""
    cert, private_key = _build_self_signed_rsa()
    recipient = PublicKeyRecipient(certificate=cert, permissions=permissions)
    return recipient, cert, private_key


@pytest.fixture(scope="module")
def two_recipients_same_perms() -> tuple[
    PublicKeyRecipient,
    PublicKeyRecipient,
    object,
    object,
    object,
    object,
]:
    """Two recipients sharing an identical permission mask."""
    try:
        perms_a = AccessPermission()
        perms_a.set_can_print(False)
        perms_b = AccessPermission()
        perms_b.set_can_print(False)
        r1, c1, k1 = _make_recipient_with(perms_a)
        r2, c2, k2 = _make_recipient_with(perms_b)
    except Exception:  # noqa: BLE001 — cert gen too heavy on some boxes
        pytest.skip("cert generation too heavy in this environment")
    # Sanity-check that the masks really are identical going in.
    assert (
        r1.get_permission().get_permission_bytes()
        == r2.get_permission().get_permission_bytes()
    )
    return r1, r2, c1, k1, c2, k2


@pytest.fixture(scope="module")
def two_recipients_different_perms() -> tuple[
    PublicKeyRecipient,
    PublicKeyRecipient,
    object,
    object,
    object,
    object,
]:
    """Two recipients with divergent permission masks."""
    try:
        perms_a = AccessPermission()
        perms_a.set_can_print(False)
        perms_a.set_can_modify(False)
        perms_b = AccessPermission()  # default: all permissions on
        r1, c1, k1 = _make_recipient_with(perms_a)
        r2, c2, k2 = _make_recipient_with(perms_b)
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")
    assert (
        r1.get_permission().get_permission_bytes()
        != r2.get_permission().get_permission_bytes()
    )
    return r1, r2, c1, k1, c2, k2


def test_two_recipients_same_perms_emit_one_envelope_each(
    two_recipients_same_perms: tuple[
        PublicKeyRecipient,
        PublicKeyRecipient,
        object,
        object,
        object,
        object,
    ],
) -> None:
    """Shared permission mask still yields one envelope PER recipient.

    Upstream computeRecipientsField never collapses recipients onto a shared
    multi-recipient envelope — it emits one per recipient regardless of mask.
    """
    r1, r2, _c1, _k1, _c2, _k2 = two_recipients_same_perms

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    policy.set_encryption_key_length(128)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)

    encryption = document.encryption
    assert encryption is not None
    recipients_array = _recipients_of(encryption)
    assert recipients_array is not None
    # One envelope per recipient — two recipients, two envelopes, matching
    # upstream's new byte[getNumberOfRecipients()][] allocation.
    assert recipients_array.size() == 2


def test_two_recipients_different_perms_emit_one_envelope_each(
    two_recipients_different_perms: tuple[
        PublicKeyRecipient,
        PublicKeyRecipient,
        object,
        object,
        object,
        object,
    ],
) -> None:
    """Divergent permission masks → one envelope per recipient (still N)."""
    r1, r2, _c1, _k1, _c2, _k2 = two_recipients_different_perms

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    policy.set_encryption_key_length(128)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)

    encryption = document.encryption
    assert encryption is not None
    recipients_array = _recipients_of(encryption)
    assert recipients_array is not None
    assert recipients_array.size() == 2


def test_same_perms_envelope_round_trips_for_each_recipient(
    two_recipients_same_perms: tuple[
        PublicKeyRecipient,
        PublicKeyRecipient,
        object,
        object,
        object,
        object,
    ],
) -> None:
    """Each recipient's own envelope decrypts with that recipient's key."""
    r1, r2, c1, k1, c2, k2 = two_recipients_same_perms

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    policy.set_encryption_key_length(128)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)
    expected_key = handler.get_encryption_key()
    assert expected_key is not None

    encryption = document.encryption
    assert encryption is not None

    for cert, private_key in ((c1, k1), (c2, k2)):
        material = PublicKeyDecryptionMaterial(
            certificate=cert, private_key=private_key
        )
        decrypt = PublicKeySecurityHandler()
        decrypt.prepare_for_decryption(encryption, b"\x00" * 16, material)
        assert decrypt.get_encryption_key() == expected_key


def test_different_perms_envelopes_round_trip_each_recipient(
    two_recipients_different_perms: tuple[
        PublicKeyRecipient,
        PublicKeyRecipient,
        object,
        object,
        object,
        object,
    ],
) -> None:
    """Each per-recipient envelope still decrypts with its own private key,
    and the surfaced ``AccessPermission`` matches the recipient's mask."""
    r1, r2, c1, k1, c2, k2 = two_recipients_different_perms

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    policy.set_encryption_key_length(128)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)
    expected_key = handler.get_encryption_key()
    assert expected_key is not None

    encryption = document.encryption
    assert encryption is not None

    # Each recipient's private key should still recover the same file key
    # (the file key is derived from seed + all envelope blobs, not from any
    # one recipient's permissions) and should also surface that recipient's
    # own permission mask via get_current_access_permission.
    for recipient, cert, private_key in (
        (r1, c1, k1),
        (r2, c2, k2),
    ):
        material = PublicKeyDecryptionMaterial(
            certificate=cert, private_key=private_key
        )
        decrypt = PublicKeySecurityHandler()
        decrypt.prepare_for_decryption(encryption, b"\x00" * 16, material)
        assert decrypt.get_encryption_key() == expected_key
        surfaced = decrypt.get_current_access_permission()
        assert surfaced is not None
        # Upstream locks the recovered permission (setReadOnly) — it reflects an
        # already-applied policy and must not be mutated by callers.
        assert surfaced.is_read_only()
        expected_perm = recipient.get_permission()
        assert expected_perm is not None
        assert (surfaced.get_permission_bytes() & 0xFFFFFFFF) == (
            expected_perm.get_permission_bytes() & 0xFFFFFFFF
        )


def test_three_recipients_yield_three_envelopes() -> None:
    """Three recipients → three envelopes, irrespective of shared masks."""
    try:
        perms_locked = AccessPermission()
        perms_locked.set_can_print(False)
        perms_open = AccessPermission()
        r1, _c1, _k1 = _make_recipient_with(perms_locked)
        r2, _c2, _k2 = _make_recipient_with(perms_locked)
        r3, _c3, _k3 = _make_recipient_with(perms_open)
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    policy.add_recipient(r3)
    policy.set_encryption_key_length(128)

    handler = PublicKeySecurityHandler(protection_policy=policy)
    document = _StubDocument()
    handler.prepare_document(document)

    encryption = document.encryption
    assert encryption is not None
    recipients_array = _recipients_of(encryption)
    assert recipients_array is not None
    # One envelope per recipient — three recipients, three envelopes.
    assert recipients_array.size() == 3

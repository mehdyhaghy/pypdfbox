"""Upstream-name parity tests for :class:`PublicKeySecurityHandler`.

Confirms the upstream-named accessor aliases (``get_protection_policy``,
``get_recipients``, ``add_recipient``, ``compute_seed_value``,
``derive_file_key``, ``is_aes``) behave the way their Java counterparts
do — empty/None defaults before a policy is attached, and round-tripping
through the attached :class:`PublicKeyProtectionPolicy`.
"""

from __future__ import annotations

import hashlib

from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import PublicKeyRecipient
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)


def test_get_protection_policy_returns_none_without_policy() -> None:
    handler = PublicKeySecurityHandler()
    assert handler.get_protection_policy() is None
    assert handler.has_protection_policy() is False


def test_get_protection_policy_returns_attached_policy() -> None:
    policy = PublicKeyProtectionPolicy()
    handler = PublicKeySecurityHandler(protection_policy=policy)
    assert handler.get_protection_policy() is policy
    assert handler.has_protection_policy() is True


def test_set_protection_policy_attaches_after_construction() -> None:
    handler = PublicKeySecurityHandler()
    policy = PublicKeyProtectionPolicy()
    handler.set_protection_policy(policy)
    assert handler.get_protection_policy() is policy


def test_get_recipients_returns_empty_list_without_policy() -> None:
    handler = PublicKeySecurityHandler()
    assert handler.get_recipients() == []


def test_get_recipients_returns_policy_recipients() -> None:
    policy = PublicKeyProtectionPolicy()
    r1 = PublicKeyRecipient()
    r2 = PublicKeyRecipient()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    handler = PublicKeySecurityHandler(protection_policy=policy)
    assert handler.get_recipients() == [r1, r2]


def test_add_recipient_lazily_creates_policy() -> None:
    handler = PublicKeySecurityHandler()
    r = PublicKeyRecipient()
    handler.add_recipient(r)
    assert isinstance(handler.get_protection_policy(), PublicKeyProtectionPolicy)
    assert handler.get_recipients() == [r]


def test_add_recipient_appends_to_existing_policy() -> None:
    policy = PublicKeyProtectionPolicy()
    r1 = PublicKeyRecipient()
    policy.add_recipient(r1)
    handler = PublicKeySecurityHandler(protection_policy=policy)
    r2 = PublicKeyRecipient()
    handler.add_recipient(r2)
    assert handler.get_recipients() == [r1, r2]


def test_is_aes_defaults_false() -> None:
    handler = PublicKeySecurityHandler()
    assert handler.is_aes() is False


def test_compute_seed_value_returns_fresh_20_byte_seed() -> None:
    handler = PublicKeySecurityHandler()
    seed1 = handler.compute_seed_value()
    seed2 = handler.compute_seed_value()
    assert isinstance(seed1, bytes)
    assert len(seed1) == 20
    # Vanishingly unlikely two os.urandom calls collide — sanity check that
    # we're not returning a constant.
    assert seed1 != seed2


def test_derive_file_key_matches_sha1_truncation_for_v4() -> None:
    handler = PublicKeySecurityHandler()
    seed = b"\x01" * 20
    blobs = [b"recipient-blob-a", b"recipient-blob-b"]
    expected = hashlib.sha1(  # noqa: S324 — non-security; mirrors PDF spec
        seed + blobs[0] + blobs[1], usedforsecurity=False
    ).digest()[:16]
    assert (
        handler.derive_file_key(seed, blobs, version=4, key_length_bits=128)
        == expected
    )


def test_derive_file_key_matches_sha256_truncation_for_v5() -> None:
    handler = PublicKeySecurityHandler()
    seed = b"\x02" * 20
    blobs = [b"only-blob"]
    expected = hashlib.sha256(seed + blobs[0]).digest()[:32]
    assert (
        handler.derive_file_key(seed, blobs, version=5, key_length_bits=256)
        == expected
    )


def test_derive_file_key_appends_ff_when_metadata_not_encrypted() -> None:
    handler = PublicKeySecurityHandler()
    seed = b"\x03" * 20
    blobs = [b"blob"]
    expected = hashlib.sha256(seed + blobs[0] + b"\xff\xff\xff\xff").digest()[:32]
    assert (
        handler.derive_file_key(
            seed, blobs, version=5, key_length_bits=256, encrypt_metadata=False
        )
        == expected
    )

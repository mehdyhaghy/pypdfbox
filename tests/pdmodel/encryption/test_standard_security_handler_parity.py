"""Upstream-named-API parity tests for ``StandardSecurityHandler``.

Covers the public accessor / helper aliases that mirror PDFBox's
``org.apache.pdfbox.pdmodel.encryption.StandardSecurityHandler`` surface:
``get_revision``, ``get_key_length``, ``is_encrypt_meta_data``,
``get_protection_policy`` / ``set_protection_policy``,
``compute_revision_number``, ``compute_user_password`` /
``compute_owner_password`` / ``compute_encrypted_key``, and
``is_user_password`` / ``is_owner_password``.
"""

from __future__ import annotations

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


# -------------------------------------------------------------- helpers


def _build_r3_encryption(
    user_pw: str, owner_pw: str, document_id: bytes
) -> PDEncryption:
    user_bytes = user_pw.encode("latin-1")
    owner_bytes = owner_pw.encode("latin-1") or user_bytes
    permissions = -3904
    o = StandardSecurityHandler.compute_owner_password(
        owner_bytes, user_bytes, 3, 16
    )
    u = StandardSecurityHandler.compute_user_password(
        user_bytes, o, permissions, document_id, 3, 16
    )
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(2)
    encryption.set_revision(3)
    encryption.set_length(128)
    encryption.set_p(permissions)
    encryption.set_o(o)
    encryption.set_u(u)
    return encryption


# -------------------------------------------------------- accessor parity


def test_get_revision_returns_configured_revision() -> None:
    handler = StandardSecurityHandler()
    handler.set_revision(4)
    assert handler.get_revision() == 4


def test_get_key_length_returns_configured_length() -> None:
    handler = StandardSecurityHandler()
    handler.set_key_length(256)
    assert handler.get_key_length() == 256


def test_is_encrypt_meta_data_alias_matches_internal_state() -> None:
    handler = StandardSecurityHandler()
    # Default per PDF 32000-1: metadata is encrypted.
    assert handler.is_encrypt_meta_data() is True
    # Both spellings stay in sync.
    assert handler.is_encrypt_metadata() == handler.is_encrypt_meta_data()


def test_get_protection_policy_returns_supplied_policy() -> None:
    policy = StandardProtectionPolicy(
        owner_password="owner",
        user_password="user",
        permissions=AccessPermission(),
    )
    handler = StandardSecurityHandler(protection_policy=policy)
    assert handler.get_protection_policy() is policy


def test_set_protection_policy_overrides_initial_policy() -> None:
    handler = StandardSecurityHandler()
    assert handler.get_protection_policy() is None
    policy = StandardProtectionPolicy("o", "u", AccessPermission())
    handler.set_protection_policy(policy)
    assert handler.get_protection_policy() is policy


# -------------------------------------------------- algo selection helper


def test_compute_revision_number_picks_r6_for_aes_256() -> None:
    assert StandardSecurityHandler.compute_revision_number(256) == 6


def test_compute_revision_number_picks_r4_for_aes_128() -> None:
    assert StandardSecurityHandler.compute_revision_number(128, prefer_aes=True) == 4


def test_compute_revision_number_picks_r3_for_rc4_128() -> None:
    assert StandardSecurityHandler.compute_revision_number(128) == 3


def test_compute_revision_number_picks_r2_for_rc4_40() -> None:
    assert StandardSecurityHandler.compute_revision_number(40) == 2


# ------------------------------------------------ password validation API


def test_is_user_password_true_for_correct_user_password_r3() -> None:
    document_id = b"\x00" * 16
    encryption = _build_r3_encryption("user", "owner", document_id)
    assert (
        StandardSecurityHandler.is_user_password("user", encryption, document_id)
        is True
    )


def test_is_user_password_false_for_wrong_password_r3() -> None:
    document_id = b"\x00" * 16
    encryption = _build_r3_encryption("user", "owner", document_id)
    assert (
        StandardSecurityHandler.is_user_password("nope", encryption, document_id)
        is False
    )


def test_is_owner_password_true_for_correct_owner_password_r3() -> None:
    document_id = b"\x00" * 16
    encryption = _build_r3_encryption("user", "owner", document_id)
    assert (
        StandardSecurityHandler.is_owner_password("owner", encryption, document_id)
        is True
    )


def test_is_owner_password_false_for_wrong_password_r3() -> None:
    document_id = b"\x00" * 16
    encryption = _build_r3_encryption("user", "owner", document_id)
    assert (
        StandardSecurityHandler.is_owner_password("nope", encryption, document_id)
        is False
    )


# ------------------------------------------------ public derivation helpers


def test_compute_encrypted_key_matches_internal_helper() -> None:
    document_id = b"\x00" * 16
    user_pw = b"user"
    owner_pw = b"owner"
    o = StandardSecurityHandler.compute_owner_password(owner_pw, user_pw, 3, 16)
    public = StandardSecurityHandler.compute_encrypted_key(
        user_pw, o, -3904, document_id, 3, 16, encrypt_metadata=True
    )
    internal = StandardSecurityHandler._compute_encryption_key(
        user_pw, o, -3904, document_id, 3, 16, encrypt_metadata=True
    )
    assert public == internal
    # Sanity: the derived file key should round-trip through the user-password
    # validator and yield the same bytes.
    encryption = _build_r3_encryption("user", "owner", document_id)
    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, document_id, StandardDecryptionMaterial("user")
    )
    assert decoder.get_encryption_key() == public


def test_compute_user_and_owner_password_aliases_match_internals() -> None:
    user_pw = b"user"
    owner_pw = b"owner"
    document_id = b"\x00" * 16
    o_alias = StandardSecurityHandler.compute_owner_password(owner_pw, user_pw, 3, 16)
    o_internal = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, 3, 16
    )
    assert o_alias == o_internal

    u_alias = StandardSecurityHandler.compute_user_password(
        user_pw, o_alias, -3904, document_id, 3, 16
    )
    u_internal = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o_internal, -3904, document_id, 3, 16
    )
    assert u_alias == u_internal

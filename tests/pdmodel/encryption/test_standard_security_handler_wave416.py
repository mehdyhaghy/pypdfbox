from __future__ import annotations

import hashlib

import pytest

from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    InvalidPasswordException,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


def test_compute_hash_revision5_is_plain_sha256() -> None:
    data = b"password" + b"12345678"

    assert (
        StandardSecurityHandler._compute_hash_r5_r6(  # noqa: SLF001
            data,
            b"password",
            b"user-key-is-ignored-for-r5" * 2,
            5,
        )
        == hashlib.sha256(data).digest()
    )


def test_r5_user_password_validation_uses_revision5_hash() -> None:
    password = b"user"
    validation_salt = b"12345678"
    key_salt = b"ABCDEFGH"
    u_value = hashlib.sha256(password + validation_salt).digest()
    encryption = PDEncryption()
    encryption.set_v(5)
    encryption.set_revision(5)
    encryption.set_length(256)
    encryption.set_p(-3904)
    encryption.set_u(u_value + validation_salt + key_salt)
    encryption.set_o(b"\x00" * 48)

    assert StandardSecurityHandler.is_user_password(password, encryption, b"") is True
    assert StandardSecurityHandler.is_user_password(b"wrong", encryption, b"") is False


def test_r5_owner_password_validation_uses_user_key_context() -> None:
    password = b"owner"
    user_key = b"u" * 48
    validation_salt = b"87654321"
    key_salt = b"HGFEDCBA"
    o_value = hashlib.sha256(password + validation_salt + user_key).digest()
    encryption = PDEncryption()
    encryption.set_v(5)
    encryption.set_revision(5)
    encryption.set_length(256)
    encryption.set_p(-3904)
    encryption.set_u(user_key)
    encryption.set_o(o_value + validation_salt + key_salt)

    assert StandardSecurityHandler.is_owner_password(password, encryption, b"") is True
    assert StandardSecurityHandler.is_owner_password(b"wrong", encryption, b"") is False


def test_revision5_short_password_entries_return_false() -> None:
    encryption = PDEncryption()
    encryption.set_v(5)
    encryption.set_revision(5)
    encryption.set_u(b"short")
    encryption.set_o(b"short")

    assert StandardSecurityHandler.is_user_password(b"user", encryption, b"") is False
    assert StandardSecurityHandler.is_owner_password(b"owner", encryption, b"") is False


def test_prepare_for_decryption_revision6_missing_key_fields_raises() -> None:
    encryption = PDEncryption()
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(-3904)
    encryption.set_o(b"\x00" * 48)
    encryption.set_u(b"\x00" * 48)

    with pytest.raises(InvalidPasswordException):
        StandardSecurityHandler().prepare_for_decryption(
            encryption,
            b"",
            StandardDecryptionMaterial("user"),
        )


def test_revision6_compute_encryption_key_returns_none_for_missing_entries() -> None:
    assert (
        StandardSecurityHandler._compute_encryption_key_r5_r6(  # noqa: SLF001
            b"pw",
            b"",
            b"u" * 48,
            b"oe" * 16,
            b"ue" * 16,
            b"perms" * 3 + b"!",
            6,
        )
        is None
    )


def test_decrypt_perms_rejects_malformed_lengths() -> None:
    assert StandardSecurityHandler._decrypt_perms_r5_r6(b"short", b"\x00" * 16) == b""  # noqa: SLF001
    assert StandardSecurityHandler._decrypt_perms_r5_r6(b"\x00" * 32, b"short") == b""  # noqa: SLF001
    assert (
        StandardSecurityHandler._validate_perms_r5_r6(  # noqa: SLF001
            b"\x00" * 32,
            b"short",
            -3904,
            True,
        )
        is False
    )


def test_aes_cfm_decrypt_short_payload_returns_empty_bytes() -> None:
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"k" * 16)
    handler._string_cfm = "AESV2"  # noqa: SLF001

    assert handler.decrypt_string(b"too short", 1, 0) == b""


def test_unknown_cfm_dispatch_is_pass_through_for_encrypt_and_decrypt() -> None:
    handler = StandardSecurityHandler()
    payload = b"leave me alone"

    assert handler._dispatch_encrypt("Mystery", payload, 1, 0) == payload  # noqa: SLF001
    assert handler._dispatch_decrypt("Mystery", payload, 1, 0) == payload  # noqa: SLF001

"""Round-trip and password-validation tests for ``StandardSecurityHandler``.

These exercise the lite port end-to-end — derive a key, push it through the
RC4 / AES per-object pipeline, then decrypt and compare. r5/r6 are tested via
the dictionary-build path (``_build_r6_dictionary``) followed by the standard
``prepare_for_decryption`` + decrypt round-trip.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    PDInvalidPasswordException,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


# ----------------------------------------------------------------- helpers


def _build_handler_r3_rc4_128(
    user_pw: str, owner_pw: str, document_id: bytes
) -> tuple[StandardSecurityHandler, PDEncryption]:
    """Build a handler + encryption dict for R=3, V=2 (RC4-128)."""
    handler = StandardSecurityHandler()
    handler.set_revision(3)
    handler.set_version(2)
    handler.set_key_length(128)
    handler.set_aes(False)

    user_bytes = user_pw.encode("latin-1")
    owner_bytes = owner_pw.encode("latin-1") or user_bytes
    permissions = -3904

    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_bytes, user_bytes, 3, 16
    )
    file_key = StandardSecurityHandler._compute_encryption_key(
        user_bytes, o, permissions, document_id, 3, 16, encrypt_metadata=True
    )
    handler.set_encryption_key(file_key)
    u = StandardSecurityHandler._compute_user_password_r2_r4(
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
    return handler, encryption


def _build_handler_r4_aes_128(
    user_pw: str, owner_pw: str, document_id: bytes
) -> tuple[StandardSecurityHandler, PDEncryption]:
    """Build a handler + encryption dict for R=4, V=4 (AES-128 w/ AESV2)."""
    handler = StandardSecurityHandler()
    handler.set_revision(4)
    handler.set_version(4)
    handler.set_key_length(128)
    handler.set_aes(True)

    user_bytes = user_pw.encode("latin-1")
    owner_bytes = owner_pw.encode("latin-1") or user_bytes
    permissions = -3904

    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_bytes, user_bytes, 4, 16
    )
    file_key = StandardSecurityHandler._compute_encryption_key(
        user_bytes, o, permissions, document_id, 4, 16, encrypt_metadata=True
    )
    handler.set_encryption_key(file_key)
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_bytes, o, permissions, document_id, 4, 16
    )

    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_length(128)
    encryption.set_p(permissions)
    encryption.set_o(o)
    encryption.set_u(u)
    encryption.set_stm_f("AESV2")
    encryption.set_str_f("AESV2")
    return handler, encryption


def _build_handler_r6_aes_256(
    user_pw: str, owner_pw: str
) -> tuple[StandardSecurityHandler, PDEncryption]:
    """Build a handler + encryption dict for R=6, V=5 (AES-256)."""
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    # Random file key — exercises the actual r6 wrap/unwrap path.
    import os

    handler.set_encryption_key(os.urandom(32))

    user_bytes = user_pw.encode("utf-8")
    owner_bytes = owner_pw.encode("utf-8") or user_bytes
    permissions = -3904
    o, oe, u, ue, perms = handler._build_r6_dictionary(
        owner_bytes, user_bytes, permissions
    )

    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(permissions)
    encryption.set_o(o)
    encryption.set_u(u)
    encryption.set_oe(oe)
    encryption.set_ue(ue)
    encryption.set_perms(perms)
    return handler, encryption


# -------------------------------------------------------------- round-trips


def test_round_trip_r3_rc4_128_user_password() -> None:
    document_id = b"\x00" * 16
    handler, encryption = _build_handler_r3_rc4_128("user", "owner", document_id)

    plaintext = b"hello rc4 world"
    ciphertext = handler.encrypt_string(plaintext, 7, 0)
    assert ciphertext != plaintext

    # Re-derive the file key from the user password and verify decrypt works.
    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, document_id, StandardDecryptionMaterial("user")
    )
    assert decoder.get_encryption_key() == handler.get_encryption_key()
    assert decoder.decrypt_string(ciphertext, 7, 0) == plaintext


def test_round_trip_r4_aes_128_user_password() -> None:
    document_id = b"\x00" * 16
    handler, encryption = _build_handler_r4_aes_128("user", "owner", document_id)

    plaintext = b"some longer payload that crosses the 16-byte AES block boundary"
    ciphertext = handler.encrypt_string(plaintext, 12, 0)
    assert ciphertext != plaintext
    # AES output = IV (16) + at least one block of ciphertext.
    assert len(ciphertext) >= 16 + 16

    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, document_id, StandardDecryptionMaterial("user")
    )
    assert decoder.is_aes() is True
    assert decoder.get_encryption_key() == handler.get_encryption_key()
    assert decoder.decrypt_string(ciphertext, 12, 0) == plaintext


def test_round_trip_r6_aes_256_user_password() -> None:
    handler, encryption = _build_handler_r6_aes_256("user", "owner")

    plaintext = b"r6 aes-256 payload"
    ciphertext = handler.encrypt_string(plaintext, 99, 0)
    assert ciphertext != plaintext

    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial("user")
    )
    assert decoder.is_aes() is True
    assert decoder.get_encryption_key() == handler.get_encryption_key()
    assert decoder.decrypt_string(ciphertext, 99, 0) == plaintext


# ----------------------------------------------------------- password paths


def test_prepare_for_decryption_wrong_password_raises() -> None:
    document_id = b"\x00" * 16
    _handler, encryption = _build_handler_r3_rc4_128("user", "owner", document_id)

    decoder = StandardSecurityHandler()
    with pytest.raises(PDInvalidPasswordException):
        decoder.prepare_for_decryption(
            encryption, document_id, StandardDecryptionMaterial("nope")
        )


def test_prepare_for_decryption_owner_password_derives_key() -> None:
    document_id = b"\x00" * 16
    handler, encryption = _build_handler_r3_rc4_128("user", "owner", document_id)

    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, document_id, StandardDecryptionMaterial("owner")
    )
    # Owner-password recovery must yield the same file key as the user path.
    assert decoder.get_encryption_key() == handler.get_encryption_key()


def test_prepare_for_decryption_owner_password_r6() -> None:
    handler, encryption = _build_handler_r6_aes_256("user", "owner")

    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial("owner")
    )
    assert decoder.get_encryption_key() == handler.get_encryption_key()


# ---------------------------------------------------------- per-object key


def test_compute_object_key_deterministic_r4() -> None:
    handler = StandardSecurityHandler()
    handler.set_revision(4)
    handler.set_version(4)
    handler.set_key_length(128)
    handler.set_aes(True)
    handler.set_encryption_key(b"\x01" * 16)

    k1 = handler.compute_object_key(7, 0)
    k2 = handler.compute_object_key(7, 0)
    k3 = handler.compute_object_key(8, 0)
    assert k1 == k2
    assert k1 != k3
    # min(n+5, 16) — AES-128 caps at 16 bytes.
    assert len(k1) == 16


def test_compute_object_key_r6_returns_file_key_directly() -> None:
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)
    file_key = b"\x42" * 32
    handler.set_encryption_key(file_key)

    assert handler.compute_object_key(1, 0) == file_key
    assert handler.compute_object_key(99, 5) == file_key


# --------------------------------------------------------------- AES flag


def test_is_aes_true_for_r4_with_aesv2() -> None:
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_length(128)
    encryption.set_p(-3904)
    encryption.set_stm_f("AESV2")
    # We need /O and /U so prepare_for_decryption can attempt validation; use
    # the values it would compute for an empty password to keep the test
    # focused on the AES detection logic.
    document_id = b"\x00" * 16
    o = StandardSecurityHandler._compute_owner_password_r2_r4(b"", b"", 4, 16)
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        b"", o, -3904, document_id, 4, 16
    )
    encryption.set_o(o)
    encryption.set_u(u)

    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        encryption, document_id, StandardDecryptionMaterial("")
    )
    assert handler.is_aes() is True


def test_is_aes_false_for_r3_rc4() -> None:
    document_id = b"\x00" * 16
    _h, encryption = _build_handler_r3_rc4_128("user", "owner", document_id)

    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, document_id, StandardDecryptionMaterial("user")
    )
    assert decoder.is_aes() is False


# -------------------------------------------------------- material + base


def test_decryption_material_password_encoding() -> None:
    assert StandardDecryptionMaterial(None).get_password() is None
    assert StandardDecryptionMaterial("hi").get_password() == b"hi"
    assert StandardDecryptionMaterial(b"raw").get_password() == b"raw"


def test_security_handler_is_abstract() -> None:
    with pytest.raises(TypeError):
        SecurityHandler()  # type: ignore[abstract]

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


# -------------------------------------------------- AES-256 (r6) coverage


def test_round_trip_r6_aes_256_empty_password() -> None:
    """ISO 32000-2 §7.6.4.4.10 — empty user password is the common case
    for ``read everything but only owner can edit`` PDFs. Both wraps must
    round-trip cleanly even when only one of (owner, user) is non-blank."""
    handler, encryption = _build_handler_r6_aes_256("", "ownerOnly")

    plaintext = b"r6 with empty user password"
    ciphertext = handler.encrypt_string(plaintext, 1, 0)
    assert ciphertext != plaintext

    # Empty user password unwraps via the user-password path.
    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial("")
    )
    assert decoder.is_aes() is True
    assert decoder.get_encryption_key() == handler.get_encryption_key()
    assert decoder.decrypt_string(ciphertext, 1, 0) == plaintext

    # Owner password must still unlock the same file.
    decoder2 = StandardSecurityHandler()
    decoder2.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial("ownerOnly")
    )
    assert decoder2.get_encryption_key() == handler.get_encryption_key()


def test_round_trip_r6_aes_256_long_payload_crosses_blocks() -> None:
    """Confirm AES-256 dispatch handles multi-block payloads — encrypted
    output must include the 16-byte IV plus a multiple of 16 bytes of
    ciphertext, and decrypt back identically."""
    handler, encryption = _build_handler_r6_aes_256("user-pw", "owner-pw")

    # Pick a payload length that is *not* a multiple of 16 so we exercise
    # the PKCS#7 padding branch end-to-end.
    plaintext = b"A" * 33 + b"B" * 17 + b"C" * 5
    ciphertext = handler.encrypt_stream(plaintext, 7, 0)
    assert ciphertext != plaintext
    assert (len(ciphertext) - 16) % 16 == 0  # IV (16) + ciphertext blocks

    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial("user-pw")
    )
    assert decoder.decrypt_stream(ciphertext, 7, 0) == plaintext


def test_r6_perms_round_trips_permission_bits() -> None:
    """``/Perms`` carries the 32-bit /P value encrypted under AES-256-ECB.
    The round-trip via ``_validate_perms_r5_r6`` must recover the exact
    permission integer the dictionary was built with."""
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    import os as _os

    handler.set_encryption_key(_os.urandom(32))
    # Custom permission set: deny printing, allow modify, deny extract.
    permissions = -1852  # arbitrary signed-32 representable value
    _o, _oe, _u, _ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner-pw", b"user-pw", permissions
    )
    assert len(perms) == 16

    # AES-256 ECB decrypt under the file key must produce the canonical
    # algorithm-10 layout.
    plain = StandardSecurityHandler._decrypt_perms_r5_r6(  # noqa: SLF001
        handler.get_encryption_key() or b"", perms
    )
    assert len(plain) == 16
    assert bytes(plain[9:12]) == b"adb"
    # First four bytes = little-endian /P.
    recovered = (
        plain[0] | (plain[1] << 8) | (plain[2] << 16) | (plain[3] << 24)
    )
    if recovered & 0x80000000:
        recovered -= 0x100000000
    assert recovered == permissions
    # Bytes 4-7 are 0xFF.
    assert plain[4:8] == b"\xff\xff\xff\xff"
    # Byte 8 is 'T' because ``encrypt_metadata`` defaults to True.
    assert plain[8:9] == b"T"
    # Validation helper agrees.
    assert StandardSecurityHandler._validate_perms_r5_r6(  # noqa: SLF001
        handler.get_encryption_key() or b"", perms, permissions, True
    ) is True
    # Tampering with the permission integer must fail validation.
    assert StandardSecurityHandler._validate_perms_r5_r6(  # noqa: SLF001
        handler.get_encryption_key() or b"", perms, permissions ^ 0xFF, True
    ) is False


def test_r6_perms_validates_encrypt_metadata_flag() -> None:
    """Byte 8 of the decrypted Perms is 'T' when EncryptMetadata is True
    and 'F' otherwise. The validation routine must agree."""
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)
    handler.set_decrypt_metadata(True)
    # Force the encrypt-metadata flag to False on the writer side.
    handler._encrypt_metadata = False  # noqa: SLF001

    import os as _os

    handler.set_encryption_key(_os.urandom(32))
    _o, _oe, _u, _ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner", b"user", -3904
    )
    plain = StandardSecurityHandler._decrypt_perms_r5_r6(  # noqa: SLF001
        handler.get_encryption_key() or b"", perms
    )
    assert plain[8:9] == b"F"
    # And validate_perms must accept it only when the caller passes
    # ``encrypt_metadata=False``.
    file_key = handler.get_encryption_key() or b""
    assert StandardSecurityHandler._validate_perms_r5_r6(  # noqa: SLF001
        file_key, perms, -3904, False
    ) is True
    assert StandardSecurityHandler._validate_perms_r5_r6(  # noqa: SLF001
        file_key, perms, -3904, True
    ) is False


def test_r6_random_salts_are_unique_per_build() -> None:
    """Each ``_build_r6_dictionary`` call must mint fresh validation +
    key salts — bytes 32-40 of /U and /O respectively, plus bytes 40-48
    each. Re-building twice on the same handler must produce different
    /O and /U values even for an identical password pair."""
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    import os as _os

    handler.set_encryption_key(_os.urandom(32))
    o1, _oe1, u1, _ue1, _p1 = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner", b"user", -3904
    )
    o2, _oe2, u2, _ue2, _p2 = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner", b"user", -3904
    )
    # Hashes will differ because OE/UE wrap a fresh file_key — but more
    # importantly the salts on /O and /U must change.
    assert o1[32:40] != o2[32:40]  # owner validation salt
    assert o1[40:48] != o2[40:48]  # owner key salt
    assert u1[32:40] != u2[32:40]  # user validation salt
    assert u1[40:48] != u2[40:48]  # user key salt


def test_compute_hash_r5_r6_user_key_below_48_is_ignored() -> None:
    """Algorithm 2.B: the user key is mixed into the per-round block only
    when its length is >= 48. Passing a shorter user_key must produce the
    same result as passing ``b""``."""
    pw = b"password"
    salt = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    h_empty = StandardSecurityHandler._compute_hash_r5_r6(  # noqa: SLF001
        pw + salt, pw, b"", 6
    )
    h_short = StandardSecurityHandler._compute_hash_r5_r6(  # noqa: SLF001
        pw + salt, pw, b"too-short", 6
    )
    assert h_empty == h_short

    # And a 48-byte user_key must produce a *different* hash — proving the
    # short-circuit is real, not a no-op masking a bug.
    h_full = StandardSecurityHandler._compute_hash_r5_r6(  # noqa: SLF001
        pw + salt, pw, b"\x00" * 48, 6
    )
    assert h_full != h_empty


def test_prepare_for_decryption_perms_mismatch_warns_but_succeeds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A corrupted /Perms field should log a warning but still let the
    decoder open the document — matches PDFBox's tolerant behaviour for
    buggy producers."""
    handler, encryption = _build_handler_r6_aes_256("user", "owner")
    # Corrupt /Perms by flipping a byte (it stays 16 bytes long so the
    # ECB decrypt still runs).
    bad = bytearray(encryption.get_perms() or b"")
    bad[0] ^= 0xFF
    encryption.set_perms(bytes(bad))

    decoder = StandardSecurityHandler()
    with caplog.at_level("WARNING"):
        decoder.prepare_for_decryption(
            encryption, b"", StandardDecryptionMaterial("user")
        )
    # Decryption still succeeded — the file_key matches the writer's.
    assert decoder.get_encryption_key() == handler.get_encryption_key()
    # And the warning fired.
    assert any("Perms" in rec.message for rec in caplog.records)

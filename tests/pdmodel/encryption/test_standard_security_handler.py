"""Round-trip and password-validation tests for ``StandardSecurityHandler``.

These exercise the lite port end-to-end — derive a key, push it through the
RC4 / AES per-object pipeline, then decrypt and compare. r5/r6 are tested via
the dictionary-build path (``_build_r6_dictionary``) followed by the standard
``prepare_for_decryption`` + decrypt round-trip.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    InvalidPasswordException,
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
    with pytest.raises(InvalidPasswordException):
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


def test_prepare_for_decryption_owner_password_r6_gets_owner_permissions() -> None:
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    import os

    handler.set_encryption_key(os.urandom(32))
    restricted = AccessPermission()
    restricted.set_can_print(False)
    permissions = restricted.get_permission_bytes()
    o, oe, u, ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner", b"user", permissions
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

    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial("owner")
    )

    current = decoder.get_current_access_permission()
    assert current is not None
    assert current.is_owner_permission()
    assert current.can_print()


def test_prepare_for_decryption_user_password_r6_keeps_limited_permissions() -> None:
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    import os

    handler.set_encryption_key(os.urandom(32))
    restricted = AccessPermission()
    restricted.set_can_print(False)
    permissions = restricted.get_permission_bytes()
    o, oe, u, ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner", b"user", permissions
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

    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial("user")
    )

    current = decoder.get_current_access_permission()
    assert current is not None
    assert not current.is_owner_permission()
    assert not current.can_print()
    assert current.is_read_only()


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


# -------------------------------------------------- r6 charset (UTF-8) tests


def test_r6_unicode_password_round_trip_utf8() -> None:
    """ISO 32000-2 §7.6.4.3.4 / PDFBOX-4155 — r6 password bytes are UTF-8.

    A password containing non-ASCII characters must round-trip when the
    same string is supplied at decryption time. (Latin-1 fallback would
    derive a different byte sequence and break the unwrap.)
    """
    user_pw = "пароль"  # Cyrillic — multi-byte under UTF-8, single-byte (lossy) under Latin-1
    owner_pw = "Schlüssel"  # German umlaut

    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    import os as _os

    handler.set_encryption_key(_os.urandom(32))
    user_bytes = user_pw.encode("utf-8")
    owner_bytes = owner_pw.encode("utf-8")
    o, oe, u, ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        owner_bytes, user_bytes, -3904
    )
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(-3904)
    encryption.set_o(o)
    encryption.set_u(u)
    encryption.set_oe(oe)
    encryption.set_ue(ue)
    encryption.set_perms(perms)

    # Decrypt with the *string* form — handler must encode as UTF-8 internally.
    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial(user_pw)
    )
    assert decoder.get_encryption_key() == handler.get_encryption_key()

    # Same with the owner string.
    decoder2 = StandardSecurityHandler()
    decoder2.prepare_for_decryption(
        encryption, b"", StandardDecryptionMaterial(owner_pw)
    )
    assert decoder2.get_encryption_key() == handler.get_encryption_key()


def test_decryption_material_get_password_bytes_charset_switch() -> None:
    """``get_password_bytes(revision)`` must return Latin-1 for r2-r4 and
    UTF-8 for r5-r6 — matching upstream's ``prepareForDecryption`` charset
    switch (PDFBOX-4155)."""
    material = StandardDecryptionMaterial("café")
    assert material.get_password_bytes(3) == "café".encode("latin-1")
    assert material.get_password_bytes(6) == "café".encode("utf-8")
    assert material.get_password_bytes(2) == b"caf\xe9"
    assert material.get_password_bytes(5) == b"caf\xc3\xa9"
    # bytes input passes through unchanged.
    raw = StandardDecryptionMaterial(b"\x00\x01\x02")
    assert raw.get_password_bytes(3) == b"\x00\x01\x02"
    assert raw.get_password_bytes(6) == b"\x00\x01\x02"
    # None stays None.
    assert StandardDecryptionMaterial(None).get_password_bytes(6) is None


def test_is_user_password_string_uses_utf8_for_r6() -> None:
    """``is_user_password(str, ...)`` must encode the supplied string as
    UTF-8 for r5/r6, otherwise Latin-1. Verify the r6 charset path against
    a non-ASCII password."""
    user_pw = "naïve"
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    import os as _os

    handler.set_encryption_key(_os.urandom(32))
    user_bytes = user_pw.encode("utf-8")
    o, oe, u, ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        user_bytes, user_bytes, -3904
    )
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(-3904)
    encryption.set_o(o)
    encryption.set_u(u)
    encryption.set_oe(oe)
    encryption.set_ue(ue)
    encryption.set_perms(perms)

    assert StandardSecurityHandler.is_user_password(user_pw, encryption, b"") is True
    assert StandardSecurityHandler.is_owner_password(user_pw, encryption, b"") is True
    # And the bytes form bypasses the charset switch entirely.
    assert (
        StandardSecurityHandler.is_user_password(user_bytes, encryption, b"")
        is True
    )


# ---------------------------------------------- Algorithm 7 inverse helper


def test_get_user_password_recovers_padded_user_pw_r3() -> None:
    """Algorithm 7's inverse: given the owner password and /O, derive the
    user-password bytes. The 32-byte result starts with the padded user
    password — verify the leading bytes match the canonical pad."""
    user_pw = b"user"
    owner_pw = b"owner"
    o = StandardSecurityHandler.compute_owner_password(owner_pw, user_pw, 3, 16)
    recovered = StandardSecurityHandler.get_user_password(owner_pw, o, 3, 16)
    # The recovered bytes should *be* the padded user password.
    expected = StandardSecurityHandler._pad_password(user_pw)  # noqa: SLF001
    assert recovered == expected


def test_get_user_password_returns_empty_for_r5_r6() -> None:
    """Upstream parity — for r5/r6, user password cannot be derived from
    the owner password (the file key is wrapped, not derived). Return
    empty bytes to match ``StandardSecurityHandler.getUserPassword``."""
    assert StandardSecurityHandler.get_user_password(b"x", b"y" * 32, 5, 32) == b""
    assert StandardSecurityHandler.get_user_password(b"x", b"y" * 32, 6, 32) == b""


def test_get_user_password_r2_with_rc4_40() -> None:
    """r2 uses a single RC4 pass; the inverse is also a single pass."""
    user_pw = b"u"
    owner_pw = b"o"
    o = StandardSecurityHandler.compute_owner_password(owner_pw, user_pw, 2, 5)
    recovered = StandardSecurityHandler.get_user_password(owner_pw, o, 2, 5)
    assert recovered == StandardSecurityHandler._pad_password(user_pw)  # noqa: SLF001


# --------------------------------------------------- cross-version dispatch


def test_compute_revision_number_consistent_with_round_trip() -> None:
    """The revision returned by ``compute_revision_number`` should match
    what ``prepare_document`` actually selects for each (key_len, prefer_aes)
    pair via the protection-policy code path."""
    from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    # (key_len, prefer_aes, expected_revision). The 40-bit row uses a permission
    # set with NO revision-3 bit so prepare_document's permission-aware revision
    # (PDFBox computeRevisionNumber: /V 1 + no rev-3 perms ⇒ R2, wave 1434)
    # agrees with the key-length-only static compute_revision_number. With the
    # default AccessPermission() (all rev-3 bits set) the 40-bit case is R3 —
    # see test_rc4_interop_oracle / test_revision_matrix_wave1367.
    cases = [
        (256, False, 6),
        (128, True, 4),
        (128, False, 3),
        (40, False, 2),
    ]
    for key_len, prefer_aes, expected_revision in cases:
        assert (
            StandardSecurityHandler.compute_revision_number(key_len, prefer_aes)
            == expected_revision
        )
        permissions = AccessPermission()
        if key_len == 40:
            permissions.set_can_fill_in_form(False)
            permissions.set_can_extract_for_accessibility(False)
            permissions.set_can_assemble_document(False)
            permissions.set_can_print_faithful(False)
        policy = StandardProtectionPolicy(
            owner_password="o",
            user_password="u",
            permissions=permissions,
        )
        policy.set_encryption_key_length(key_len)
        policy.set_prefer_aes(prefer_aes)
        handler = StandardSecurityHandler(protection_policy=policy)
        # Drive prepare_document with a bare object that exposes only the
        # methods the handler reaches for.
        class _DocStub:
            def __init__(self) -> None:
                self.encryption: PDEncryption | None = None

            def set_encryption_dictionary(self, e: PDEncryption) -> None:
                self.encryption = e

        doc = _DocStub()
        handler.prepare_document(doc)
        assert handler.get_revision() == expected_revision


# --------------------------------------------------------------- upstream API
# Smoke tests for the upstream-named parity aliases — each delegates to an
# existing implementation so we mainly check (a) the alias resolves and (b)
# it produces output identical to its private/snake-renamed counterpart.


def test_truncate127_alias_matches_truncate_127() -> None:
    payload = bytes(range(200))
    assert StandardSecurityHandler.truncate127(payload) == (
        StandardSecurityHandler.truncate_127(payload)
    )
    assert len(StandardSecurityHandler.truncate127(payload)) == 127


def test_compute_sha256_alias_matches_compute_sha_256() -> None:
    pw, salt = b"password", b"saltsalt"
    assert StandardSecurityHandler.compute_sha256(pw, salt, b"") == (
        StandardSecurityHandler.compute_sha_256(pw, salt, b"")
    )


def test_compute_hash2_a_and_2_b_aliases_match_underscore_forms() -> None:
    pw, salt = b"x" * 8, b"y" * 8
    assert StandardSecurityHandler.compute_hash2_a(pw, salt, b"") == (
        StandardSecurityHandler.compute_hash_2a(pw, salt, b"")
    )
    inp = b"a" * 16
    assert StandardSecurityHandler.compute_hash2_b(inp, pw, b"") == (
        StandardSecurityHandler.compute_hash_2b(inp, pw, b"")
    )


def test_compute_rc4key_alias_matches_compute_rc_4_key() -> None:
    pw = b"owner-password"
    for rev in (2, 3, 4):
        length = 5 if rev == 2 else 16
        assert StandardSecurityHandler.compute_rc4key(pw, rev, length) == (
            StandardSecurityHandler.compute_rc_4_key(pw, rev, length)
        )


def test_compute_encrypted_key_rev234_matches_internal_helper() -> None:
    pw, o, perms, doc_id = b"user", b"O" * 32, -3904, b"\x00" * 16
    expected = StandardSecurityHandler._compute_encryption_key(
        pw, o, perms, doc_id, 3, 16, True
    )
    assert StandardSecurityHandler.compute_encrypted_key_rev234(
        pw, o, perms, doc_id, True, 16, 3
    ) == expected


def test_get_user_password234_round_trips_owner_to_user_padding() -> None:
    user_pw = b"u" * 6
    owner_pw = b"o" * 6
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, 3, 16
    )
    recovered = StandardSecurityHandler.get_user_password234(owner_pw, o, 3, 16)
    # First 32 bytes should be the padded user password.
    assert recovered[:32] == StandardSecurityHandler.truncate_or_pad(user_pw)


def test_is_user_password234_and_56_aliases_match_underscore_forms() -> None:
    user_pw = b"u" * 6
    owner_pw = b"o" * 6
    doc_id = b"\x00" * 16
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, 3, 16
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, -3904, doc_id, 3, 16
    )
    assert StandardSecurityHandler.is_user_password234(
        user_pw, u, o, -3904, doc_id, 3, 16, True
    )
    assert not StandardSecurityHandler.is_user_password234(
        b"wrong", u, o, -3904, doc_id, 3, 16, True
    )


def test_is_owner_password234_recognises_owner_pw() -> None:
    user_pw = b"user-pw"
    owner_pw = b"owner-pw"
    doc_id = b"\x00" * 16
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, 3, 16
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, -3904, doc_id, 3, 16
    )
    assert StandardSecurityHandler.is_owner_password234(
        owner_pw, u, o, -3904, doc_id, 3, 16, True
    )


def test_concat_two_and_three_arg_match_upstream_overloads() -> None:
    assert StandardSecurityHandler.concat(b"ab", b"cd") == b"abcd"
    assert StandardSecurityHandler.concat(b"ab", b"cd", b"ef") == b"abcdef"
    # No args — empty bytes (mirrors Java's zero-length output).
    assert StandardSecurityHandler.concat() == b""


def test_get_document_id_bytes_alias_handles_none_and_bytes() -> None:
    assert StandardSecurityHandler.get_document_id_bytes(None) == b""
    assert StandardSecurityHandler.get_document_id_bytes(b"abc") == b"abc"


def test_log_if_strong_encryption_missing_is_a_safe_noop() -> None:
    # Python's cryptography backend always supports full key lengths, so this
    # mirror is a no-op. The contract is "doesn't raise".
    assert StandardSecurityHandler.log_if_strong_encryption_missing() is None


def test_prepare_encryption_dict_aes_installs_aesv2_filter() -> None:
    handler = StandardSecurityHandler()
    handler.set_key_length(128)
    encryption = PDEncryption()
    handler.prepare_encryption_dict_aes(encryption, "AESV2")
    assert handler.is_aes() is True
    assert encryption.get_stm_f() == "StdCF"
    assert encryption.get_str_f() == "StdCF"
    std_cf = encryption.get_crypt_filter_dictionary("StdCF")
    assert std_cf is not None
    assert std_cf.get_cfm() == "AESV2"


def test_prepare_encryption_dict_rev234_round_trip_r3() -> None:
    handler = StandardSecurityHandler()
    handler.set_revision(3)
    handler.set_version(2)
    handler.set_key_length(128)
    encryption = PDEncryption()
    encryption.set_filter("Standard")

    class _Doc:
        pass

    handler.prepare_encryption_dict_rev234(
        owner_password="owner",
        user_password="user",
        encryption_dictionary=encryption,
        permission_int=-3904,
        document=_Doc(),
        revision=3,
        length=16,
    )
    assert encryption.get_o() is not None and len(encryption.get_o()) == 32
    assert encryption.get_u() is not None and len(encryption.get_u()) == 32
    assert handler.get_encryption_key() is not None
    assert len(handler.get_encryption_key()) == 16


def test_prepare_encryption_dict_rev6_writes_full_r6_dict() -> None:
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    handler.prepare_encryption_dict_rev6(
        owner_password="owner",
        user_password="user",
        encryption_dictionary=encryption,
        permission_int=-3904,
    )
    # /U, /UE, /O, /OE all exactly 48 / 32 bytes per the spec.
    assert encryption.get_u() is not None and len(encryption.get_u()) == 48
    assert encryption.get_o() is not None and len(encryption.get_o()) == 48
    assert encryption.get_ue() is not None and len(encryption.get_ue()) == 32
    assert encryption.get_oe() is not None and len(encryption.get_oe()) == 32
    assert encryption.get_perms() is not None and len(encryption.get_perms()) == 16
    # AESV3 crypt filter wired up.
    std_cf = encryption.get_crypt_filter_dictionary("StdCF")
    assert std_cf is not None and std_cf.get_cfm() == "AESV3"


def test_compute_encrypted_key_rev56_round_trips_user_password() -> None:
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    encryption = PDEncryption()
    handler.prepare_encryption_dict_rev6(
        owner_password="owner",
        user_password="user",
        encryption_dictionary=encryption,
        permission_int=-3904,
    )
    expected_key = handler.get_encryption_key()
    recovered = StandardSecurityHandler.compute_encrypted_key_rev56(
        b"user",
        False,
        encryption.get_o(),
        encryption.get_u(),
        encryption.get_oe(),
        encryption.get_ue(),
        6,
    )
    assert recovered == expected_key


def test_compute_encrypted_key_rev56_owner_missing_oe_raises() -> None:
    with pytest.raises(OSError):
        StandardSecurityHandler.compute_encrypted_key_rev56(
            b"owner",
            True,
            b"O" * 48,
            b"U" * 48,
            None,
            b"\x00" * 32,
            6,
        )

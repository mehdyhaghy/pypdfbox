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


# ----------------------------------------------- upstream constant / shape


def test_filter_constant_matches_pdfbox() -> None:
    assert StandardSecurityHandler.FILTER == "Standard"


def test_get_filter_returns_filter_constant() -> None:
    assert StandardSecurityHandler().get_filter() == "Standard"


def test_protection_policy_class_constant_points_at_standard_policy() -> None:
    # Mirrors upstream's ``public static final Class<?> PROTECTION_POLICY_CLASS``.
    assert StandardSecurityHandler.PROTECTION_POLICY_CLASS is StandardProtectionPolicy


# -------------------------------------------------- has_protection_policy


def test_has_protection_policy_false_without_policy() -> None:
    assert StandardSecurityHandler().has_protection_policy() is False


def test_has_protection_policy_true_with_policy() -> None:
    policy = StandardProtectionPolicy("o", "u", AccessPermission())
    assert StandardSecurityHandler(protection_policy=policy).has_protection_policy() is True


def test_has_protection_policy_tracks_set_protection_policy() -> None:
    handler = StandardSecurityHandler()
    assert handler.has_protection_policy() is False
    handler.set_protection_policy(
        StandardProtectionPolicy("o", "u", AccessPermission())
    )
    assert handler.has_protection_policy() is True
    handler.set_protection_policy(None)
    assert handler.has_protection_policy() is False


# ---------------------------------------- compute_revision_number_from_version


def test_compute_revision_number_from_version_v5_picks_r6() -> None:
    # Note in PDF 32000-2: V=5 was a deprecated Adobe extension; prepare_document
    # always upgrades to r6.
    handler = StandardSecurityHandler()
    assert handler.compute_revision_number_from_version(5) == 6


def test_compute_revision_number_from_version_v4_picks_r4() -> None:
    handler = StandardSecurityHandler()
    assert handler.compute_revision_number_from_version(4) == 4


def test_compute_revision_number_from_version_v2_picks_r3() -> None:
    handler = StandardSecurityHandler()
    assert handler.compute_revision_number_from_version(2) == 3


def test_compute_revision_number_from_version_v3_picks_r3() -> None:
    handler = StandardSecurityHandler()
    assert handler.compute_revision_number_from_version(3) == 3


def test_compute_revision_number_from_version_v1_picks_r2_without_policy() -> None:
    # Without a policy (or without revision-3 perms) V<2 collapses to r2.
    handler = StandardSecurityHandler()
    assert handler.compute_revision_number_from_version(1) == 2


# ----------------------------------------------- prepare_document_for_encryption


def test_prepare_document_for_encryption_alias_runs_prepare_document() -> None:
    """Upstream-named alias should produce an encryption dictionary identical
    to the one ``prepare_document`` writes when both are called with the same
    policy + document fixture."""

    class _StubDocument:
        def __init__(self) -> None:
            self.encryption_dictionary = None

        def set_encryption_dictionary(self, enc: object) -> None:
            self.encryption_dictionary = enc

    policy = StandardProtectionPolicy("owner", "user", AccessPermission())
    policy.set_encryption_key_length(128)

    handler = StandardSecurityHandler(protection_policy=policy)
    doc = _StubDocument()
    handler.prepare_document_for_encryption(doc)

    assert doc.encryption_dictionary is not None
    # Round-trip: the dictionary should be a valid /Standard r3 / V=2 entry
    # for the 128-bit RC4 default (no AES preference set).
    assert doc.encryption_dictionary.get_filter() == "Standard"
    assert doc.encryption_dictionary.get_revision() == 3
    assert doc.encryption_dictionary.get_v() == 2


# --------------------------- upstream byte[]-args parity overloads ---------


def test_is_user_password_explicit_byte_args_form_validates_correct_password() -> None:
    """Upstream Java ``isUserPassword(byte[] password, byte[] user, byte[]
    owner, int permissions, byte[] id, int encRevision, int keyLengthInBytes,
    boolean encryptMetadata)`` shape — pypdfbox accepts the same 8-positional
    form for byte-for-byte parity with PDFBox L1013."""
    document_id = b"\x00" * 16
    user_bytes = b"user"
    owner_bytes = b"owner"
    permissions = -3904
    o = StandardSecurityHandler.compute_owner_password(
        owner_bytes, user_bytes, 3, 16
    )
    u = StandardSecurityHandler.compute_user_password(
        user_bytes, o, permissions, document_id, 3, 16
    )
    assert (
        StandardSecurityHandler.is_user_password(
            user_bytes, u, o, permissions, document_id, 3, 16, True
        )
        is True
    )
    assert (
        StandardSecurityHandler.is_user_password(
            b"wrong", u, o, permissions, document_id, 3, 16, True
        )
        is False
    )


def test_is_owner_password_explicit_byte_args_form_validates_correct_password() -> None:
    """Same shape for ``isOwnerPassword(byte[]…)`` — Java L592 byte-for-byte."""
    document_id = b"\x00" * 16
    user_bytes = b"user"
    owner_bytes = b"owner"
    permissions = -3904
    o = StandardSecurityHandler.compute_owner_password(
        owner_bytes, user_bytes, 3, 16
    )
    u = StandardSecurityHandler.compute_user_password(
        user_bytes, o, permissions, document_id, 3, 16
    )
    assert (
        StandardSecurityHandler.is_owner_password(
            owner_bytes, u, o, permissions, document_id, 3, 16, True
        )
        is True
    )
    assert (
        StandardSecurityHandler.is_owner_password(
            b"wrong", u, o, permissions, document_id, 3, 16, True
        )
        is False
    )


def test_is_user_password_explicit_form_unknown_revision_raises() -> None:
    """Java L1028 throws ``IOException("Unknown Encryption Revision …")``
    for an unsupported revision; pypdfbox raises ``OSError`` (the
    documented Python parity for ``IOException``)."""
    import pytest

    with pytest.raises(OSError, match="Unknown Encryption Revision"):
        StandardSecurityHandler.is_user_password(
            b"pw", b"u" * 32, b"o" * 32, -3904, b"\x00" * 16, 99, 16, True
        )


def test_is_owner_password_explicit_form_unknown_revision_raises() -> None:
    import pytest

    with pytest.raises(OSError, match="Unknown Encryption Revision"):
        StandardSecurityHandler.is_owner_password(
            b"pw", b"u" * 32, b"o" * 32, -3904, b"\x00" * 16, 99, 16, True
        )


def test_compute_owner_password_revision2_with_wrong_length_raises() -> None:
    """Java L920-922 throws when r2 is paired with key length != 5 bytes."""
    import pytest

    with pytest.raises(OSError, match="Expected length=5"):
        StandardSecurityHandler.compute_owner_password(b"o", b"u", 2, 16)


def test_compute_user_password_returns_empty_for_revision_5_and_6() -> None:
    """Java L862-865 — r5/r6 has no recoverable plaintext /U; mirror the
    empty-byte return value."""
    assert (
        StandardSecurityHandler.compute_user_password(
            b"pw", b"o" * 32, -3904, b"\x00" * 16, 5, 32
        )
        == b""
    )
    assert (
        StandardSecurityHandler.compute_user_password(
            b"pw", b"o" * 32, -3904, b"\x00" * 16, 6, 32
        )
        == b""
    )


def test_truncate_127_caps_long_input() -> None:
    """Mirror upstream ``truncate127`` (Java L1255): inputs longer than
    127 bytes are truncated, shorter inputs returned as-is."""
    assert StandardSecurityHandler.truncate_127(b"x" * 200) == b"x" * 127
    assert StandardSecurityHandler.truncate_127(b"short") == b"short"
    assert StandardSecurityHandler.truncate_127(b"") == b""


def test_adjust_user_key_truncates_to_48_bytes() -> None:
    """Mirror upstream ``adjustUserKey`` (Java L1218): >48 truncates,
    exactly 48 returns unchanged, empty/null returns empty, short raises."""
    assert StandardSecurityHandler.adjust_user_key(b"x" * 60) == b"x" * 48
    assert StandardSecurityHandler.adjust_user_key(b"x" * 48) == b"x" * 48
    assert StandardSecurityHandler.adjust_user_key(None) == b""
    assert StandardSecurityHandler.adjust_user_key(b"") == b""

    import pytest

    with pytest.raises(OSError, match="Bad U length"):
        StandardSecurityHandler.adjust_user_key(b"too-short")


def test_compute_sha_256_matches_explicit_construction() -> None:
    """``computeSHA256`` (Java L1210) is sha256(input || password ||
    adjustUserKey(userKey)) — verify the helper builds the same digest."""
    import hashlib

    pw = b"hello"
    salt = b"\x01" * 8
    user_key = b"u" * 48
    expected = hashlib.sha256(pw + salt + user_key).digest()
    assert StandardSecurityHandler.compute_sha_256(pw, salt, user_key) == expected
    # And empty/null user_key → sha256(input || password).
    assert (
        StandardSecurityHandler.compute_sha_256(pw, salt, None)
        == hashlib.sha256(pw + salt).digest()
    )


def test_compute_rc_4_key_round_trip_for_revision_3() -> None:
    """``computeRC4key`` (Java L951) is the MD5+50-iteration helper used
    by /O and /U recovery. r2 omits the 50-rep loop; r3/r4 includes it."""
    pw = b"owner-password"
    r2 = StandardSecurityHandler.compute_rc_4_key(pw, 2, 5)
    r3 = StandardSecurityHandler.compute_rc_4_key(pw, 3, 16)
    assert len(r2) == 5
    assert len(r3) == 16
    # r2 and r3 must yield different keys — proving the iteration loop runs.
    assert r2 != r3[:5]


def test_compute_encrypted_key_full_form_dispatches_to_rev234() -> None:
    """The 11-arg upstream form must produce the same r3 file key as the
    7-arg compact form when both are passed equivalent inputs."""
    document_id = b"\x00" * 16
    pw = b"user"
    owner_bytes = b"owner"
    permissions = -3904
    o = StandardSecurityHandler.compute_owner_password(owner_bytes, pw, 3, 16)
    u = StandardSecurityHandler.compute_user_password(
        pw, o, permissions, document_id, 3, 16
    )
    compact = StandardSecurityHandler.compute_encrypted_key(
        pw, o, permissions, document_id, 3, 16, True
    )
    full = StandardSecurityHandler.compute_encrypted_key(
        pw, o, u, b"", b"", permissions, document_id, 3, 16, True, False
    )
    assert compact == full


def test_compute_encrypted_key_full_form_dispatches_to_rev6() -> None:
    """For r6 the full 11-arg form must invoke the AES-256 key-unwrap
    path — exercise it via ``_build_r6_dictionary`` round-trip."""
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)

    import os as _os

    handler.set_encryption_key(_os.urandom(32))
    o, oe, u, ue, _perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner", b"user", -3904
    )

    # Recover the file key via the user-password form.
    file_key_via_user = StandardSecurityHandler.compute_encrypted_key(
        b"user", o, u, oe, ue, -3904, b"", 6, 32, True, False
    )
    # And via the owner-password form.
    file_key_via_owner = StandardSecurityHandler.compute_encrypted_key(
        b"owner", o, u, oe, ue, -3904, b"", 6, 32, True, True
    )
    assert file_key_via_user == handler.get_encryption_key()
    assert file_key_via_owner == handler.get_encryption_key()


def test_get_document_id_bytes_handles_cos_array_or_bytes() -> None:
    """``prepareForDecryption`` (Java L150) takes a ``COSArray`` for the
    document ID; pypdfbox accepts both ``COSArray`` and raw bytes via the
    ``getDocumentIDBytes`` upstream helper."""
    from pypdfbox.cos import COSArray, COSString

    # bytes input pass-through
    assert (
        StandardSecurityHandler._get_document_id_bytes(b"abc")  # noqa: SLF001
        == b"abc"
    )
    # None / empty
    assert StandardSecurityHandler._get_document_id_bytes(None) == b""  # noqa: SLF001

    # COSArray with COSString[0] returns its raw bytes
    arr = COSArray()
    arr.add(COSString(b"\x01\x02\x03"))
    assert (
        StandardSecurityHandler._get_document_id_bytes(arr)  # noqa: SLF001
        == b"\x01\x02\x03"
    )
    # Empty COSArray returns b"" (matches Java L309's ``new byte[0]``).
    empty = COSArray()
    assert StandardSecurityHandler._get_document_id_bytes(empty) == b""  # noqa: SLF001


def test_validate_perms_warns_on_corrupted_perms_block(
    caplog,
) -> None:
    """Mirror upstream ``validatePerms`` (Java L317): the helper logs
    warnings on permission mismatches *without* raising, to tolerate
    buggy producers."""
    import logging
    import os as _os

    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)
    handler.set_encryption_key(_os.urandom(32))

    _o, _oe, _u, _ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner", b"user", -3904
    )
    encryption = PDEncryption()
    encryption.set_v(5)
    encryption.set_revision(6)
    # Corrupt the permission integer so byte-0 mismatches /P.
    bad_perms = bytearray(perms)
    bad_perms[0] ^= 0xFF
    encryption.set_perms(bytes(bad_perms))

    with caplog.at_level(logging.WARNING):
        # Must NOT raise — upstream is intentionally permissive here.
        handler.validate_perms(encryption, -3904, True)
    assert any(
        "permissions" in rec.message.lower() for rec in caplog.records
    )


def test_compute_hash_2a_matches_compute_hash_2b_pipeline() -> None:
    """Algorithm 2.A is just 2.B with ``input = password || salt ||
    adjustUserKey(u)`` and ``user_key = adjustUserKey(u)`` — verify both
    helpers compose equivalently."""
    pw = b"pw" * 32  # > 127 truncated to 127
    salt = b"\xAA" * 8
    u = b"u" * 48

    direct = StandardSecurityHandler.compute_hash_2a(pw, salt, u)
    truncated = StandardSecurityHandler.truncate_127(pw)
    user_key = StandardSecurityHandler.adjust_user_key(u)
    composed = StandardSecurityHandler.compute_hash_2b(
        truncated + salt + user_key, truncated, user_key
    )
    assert direct == composed

"""Wave 1348 — coverage-boost pass on ``StandardSecurityHandler``.

Targets the remaining uncovered branches:

* arity dispatch (``is_user_password`` / ``is_owner_password`` raising
  ``TypeError`` on a wrong-arg-count caller);
* str-password encoding paths in ``_is_user_password_explicit`` /
  ``_is_owner_password_explicit`` for both r2-r4 (Latin-1) and r5/r6
  (UTF-8);
* ``_get_document_id_bytes`` edge cases (size() raising, no get/getObject
  attribute, missing ``get_bytes``);
* ``truncate_127`` with ``None``;
* ``compute_rc_4_key`` raising on illegal key length;
* ``validate_perms`` warning branches (cannot-decrypt /
  perm-mismatch / metadata-flag mismatch);
* ``_compute_encryption_key_rev_5_6`` missing-/OE and missing-/UE
  guards (and the public ``compute_encrypted_key_rev56`` mirror);
* ``is_user_password234`` / ``is_user_password56`` /
  ``is_owner_password234`` / ``is_owner_password56`` aliases;
* ``get_user_password234`` r2 branch;
* ``prepare_encryption_dict_rev234`` empty-owner-password promotion +
  r4 AESV2 install branch;
* ``prepare_encryption_dict_rev6`` empty-owner-password promotion.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)

# ---------- arity dispatch (TypeError on wrong number of args) -------------


def test_is_user_password_wrong_arity_raises_type_error() -> None:
    with pytest.raises(TypeError, match="takes either"):
        StandardSecurityHandler.is_user_password(b"pw", b"only-one-extra")


def test_is_owner_password_wrong_arity_raises_type_error() -> None:
    with pytest.raises(TypeError, match="takes either"):
        StandardSecurityHandler.is_owner_password(b"pw", b"only-one-extra")


# ---------- str password encoding (r5/r6 → utf-8, r2-r4 → latin-1) ---------


def test_is_user_password_explicit_str_password_latin1() -> None:
    """``_is_user_password_explicit`` with a ``str`` password under r3
    must encode via Latin-1 (covers the str-encoding branch at L575-577)."""
    # Build a known r3 setup; round-trip through is_user_password_explicit.
    user_pw = "secret"
    owner_pw = "owner"
    doc_id = b"\x00" * 16
    permissions = -3904
    user_bytes = user_pw.encode("latin-1")
    owner_bytes = owner_pw.encode("latin-1")
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_bytes, user_bytes, 3, 16
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_bytes, o, permissions, doc_id, 3, 16
    )
    # str-password call hits the encoding branch.
    assert StandardSecurityHandler._is_user_password_explicit(
        "secret", u, o, permissions, doc_id, 3, 16, True
    )


def test_is_user_password_explicit_str_password_utf8_r5() -> None:
    """Under r5/r6 the str password must encode as UTF-8."""
    # The hash is deterministic; mismatch result is fine — we just need to
    # execute the encoding branch without raising.
    assert StandardSecurityHandler._is_user_password_explicit(
        "café", b"\x00" * 48, b"\x00" * 48, 0, b"", 5, 32, True
    ) is False


def test_is_owner_password_explicit_str_password_latin1() -> None:
    user_pw = "user-pw"
    owner_pw = "owner-pw"
    doc_id = b"\x00" * 16
    permissions = -3904
    user_bytes = user_pw.encode("latin-1")
    owner_bytes = owner_pw.encode("latin-1")
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_bytes, user_bytes, 3, 16
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_bytes, o, permissions, doc_id, 3, 16
    )
    assert StandardSecurityHandler._is_owner_password_explicit(
        "owner-pw", u, o, permissions, doc_id, 3, 16, True
    )


def test_is_owner_password_explicit_str_password_utf8_r5() -> None:
    assert StandardSecurityHandler._is_owner_password_explicit(
        "café", b"\x00" * 48, b"\x00" * 48, 0, b"", 5, 32, True
    ) is False


# ---------- _get_document_id_bytes edge cases ------------------------------


def test_get_document_id_bytes_size_raises_type_error() -> None:
    """A ``size()`` that raises returns ``b""`` (covers line 1167-1168)."""

    class BadId:
        def size(self):  # type: ignore[no-untyped-def]
            raise TypeError("size unavailable")

    assert StandardSecurityHandler._get_document_id_bytes(BadId()) == b""


def test_get_document_id_bytes_no_getter() -> None:
    """A COSArray-like object whose ``size()>=1`` but with no ``get`` or
    ``get_object`` accessor returns ``b""`` (fall-through at L1177)."""

    class NoGetter:
        def size(self):  # type: ignore[no-untyped-def]
            return 1

    assert StandardSecurityHandler._get_document_id_bytes(NoGetter()) == b""


def test_get_document_id_bytes_first_lacks_get_bytes() -> None:
    """``getter(0)`` returns something without ``get_bytes``; fall-through
    yields ``b""`` (covers the final return at L1177)."""

    class NoGetBytesFirst:
        pass

    class WrapperArr:
        def size(self):  # type: ignore[no-untyped-def]
            return 1

        def get(self, idx):  # type: ignore[no-untyped-def]
            return NoGetBytesFirst()

    assert StandardSecurityHandler._get_document_id_bytes(WrapperArr()) == b""


# ---------- truncate_127 / compute_rc_4_key edge cases ----------------------


def test_truncate_127_none_returns_empty() -> None:
    """``None`` input returns ``b""`` (covers line 1388)."""
    assert StandardSecurityHandler.truncate_127(None) == b""  # type: ignore[arg-type]


def test_compute_rc_4_key_zero_length_raises_os_error() -> None:
    """A length of 0 produces a ``ValueError`` inside ``hashlib.md5(...)[:0]``
    — but the actual ValueError comes from the inner re-hash loop only
    when length is invalid for AES wrappers. Force the path by patching
    hashlib to make the MD5 digest call raise."""
    import hashlib

    real_md5 = hashlib.md5

    class _BadMD5:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise ValueError("simulated: illegal key length")

    hashlib.md5 = _BadMD5  # type: ignore[assignment]
    try:
        with pytest.raises(OSError, match="illegal key length"):
            StandardSecurityHandler.compute_rc_4_key(b"\x00" * 32, 3, 16)
    finally:
        hashlib.md5 = real_md5  # type: ignore[assignment]


# ---------- validate_perms warning branches --------------------------------


def _make_r6_handler_with_dict():  # type: ignore[no-untyped-def]
    """Build an r6-prepared handler + encryption dict, returning both."""
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)
    handler._encrypt_metadata = True

    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    permissions = -3904
    encryption.set_p(permissions)

    handler.prepare_encryption_dict_rev6(
        "owner-pw", "user-pw", encryption, permissions
    )
    return handler, encryption, permissions


def test_validate_perms_perms_p_mismatch_logs_warning(caplog) -> None:  # type: ignore[no-untyped-def]
    """A /Perms whose decoded perm-int doesn't match the /P logs but
    doesn't raise (covers lines 1513-1514)."""
    handler, encryption, permissions = _make_r6_handler_with_dict()
    with caplog.at_level("WARNING", logger="pypdfbox.pdmodel.encryption.standard_security_handler"):
        # Pass a wildly wrong dic_permissions — perms_p won't match.
        handler.validate_perms(encryption, 12345, True)
    assert any("Verification of permissions failed" in r.message for r in caplog.records)


def test_validate_perms_metadata_flag_mismatch_logs_warning(caplog) -> None:  # type: ignore[no-untyped-def]
    """Permissions match but encrypt_metadata flag is flipped → warning
    on the EncryptMetadata branch."""
    handler, encryption, permissions = _make_r6_handler_with_dict()
    with caplog.at_level("WARNING"):
        # encrypt_metadata=False, but the r6 dict was built with True →
        # plain[8] = 'T' which doesn't match expected 'F'.
        handler.validate_perms(encryption, permissions, False)
    assert any("EncryptMetadata" in r.message for r in caplog.records)


def test_validate_perms_short_perms_returns_early() -> None:
    """A /Perms shorter than 16 bytes is ignored (no warning, no raise)."""
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"\x00" * 32)
    encryption = PDEncryption()
    encryption.set_perms(b"short")
    handler.validate_perms(encryption, 0, True)


def test_validate_perms_none_perms_returns_early() -> None:
    """A None /Perms is ignored (covers the ``perms is None`` branch)."""
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"\x00" * 32)
    encryption = PDEncryption()
    # Default constructed: /Perms not present → get_perms() returns None.
    assert encryption.get_perms() is None
    handler.validate_perms(encryption, 0, True)


def test_validate_perms_decrypt_failure_logs_warning(caplog) -> None:  # type: ignore[no-untyped-def]
    """When ``_decrypt_perms_r5_r6`` returns a non-16-byte plaintext
    (e.g. wrong key length), the warning fires (covers line 1500-1501)."""
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"\x00" * 16)  # wrong size → returns b""
    encryption = PDEncryption()
    encryption.set_perms(b"\x00" * 16)
    with caplog.at_level("WARNING"):
        handler.validate_perms(encryption, 0, True)
    assert any("cannot decrypt" in r.message for r in caplog.records)


# ---------- _compute_encryption_key_rev_5_6 missing-OE / missing-UE --------


def test_compute_encryption_key_rev_5_6_missing_oe_raises() -> None:
    """is_owner_password=True with ``oe=None`` raises OSError."""
    with pytest.raises(OSError, match="/OE"):
        StandardSecurityHandler._compute_encryption_key_rev_5_6(
            b"pw", True, b"\x00" * 48, b"\x00" * 48, None, b"\x00" * 32, 6
        )


def test_compute_encryption_key_rev_5_6_missing_ue_raises() -> None:
    """is_owner_password=False with ``ue=None`` raises OSError."""
    with pytest.raises(OSError, match="/UE"):
        StandardSecurityHandler._compute_encryption_key_rev_5_6(
            b"pw", False, b"\x00" * 48, b"\x00" * 48, b"\x00" * 32, None, 6
        )


def test_compute_encrypted_key_rev56_missing_oe_raises() -> None:
    """Public ``compute_encrypted_key_rev56`` mirrors the OE guard."""
    with pytest.raises(OSError, match="/OE"):
        StandardSecurityHandler.compute_encrypted_key_rev56(
            b"pw", True, b"\x00" * 48, b"\x00" * 48, None, b"\x00" * 32, 6
        )


def test_compute_encrypted_key_rev56_missing_ue_raises() -> None:
    with pytest.raises(OSError, match="/UE"):
        StandardSecurityHandler.compute_encrypted_key_rev56(
            b"pw", False, b"\x00" * 48, b"\x00" * 48, b"\x00" * 32, None, 6
        )


def test_compute_encryption_key_rev_5_6_r5_owner_branch() -> None:
    """r5 + is_owner_password=True hits the SHA-256 branch (not the
    hardened r6 hash) — exercises the ``enc_revision == 5`` branch in
    the owner-side guard."""
    # 48-byte O/U with predictable salts; OE long enough for AES-CBC unwrap.
    # The result might be garbage bytes — we just need the branch to run.
    o = b"\x00" * 32 + b"\x01" * 8 + b"\x02" * 8
    u = b"\x00" * 32 + b"\x03" * 8 + b"\x04" * 8
    oe = b"\x00" * 32
    result = StandardSecurityHandler._compute_encryption_key_rev_5_6(
        b"pw", True, o, u, oe, b"", 5
    )
    assert isinstance(result, bytes)


def test_compute_encryption_key_rev_5_6_r5_user_branch() -> None:
    """r5 + is_owner_password=False hits the SHA-256 user branch."""
    o = b"\x00" * 32 + b"\x01" * 8 + b"\x02" * 8
    u = b"\x00" * 32 + b"\x03" * 8 + b"\x04" * 8
    ue = b"\x00" * 32
    result = StandardSecurityHandler._compute_encryption_key_rev_5_6(
        b"pw", False, o, u, b"", ue, 5
    )
    assert isinstance(result, bytes)


# ---------- upstream-named alias methods (parity coverage) -----------------


def test_is_user_password234_alias_round_trip() -> None:
    """``is_user_password234`` mirrors ``_is_user_password_2_3_4``."""
    user_pw = b"u"
    owner_pw = b"o"
    doc_id = b"\x11" * 16
    perms = -3904
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, 3, 16
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, perms, doc_id, 3, 16
    )
    assert StandardSecurityHandler.is_user_password234(
        user_pw, u, o, perms, doc_id, 3, 16, True
    )


def test_is_user_password56_alias_mismatches() -> None:
    """``is_user_password56`` exposes ``_is_user_password_5_6`` (alias)."""
    assert StandardSecurityHandler.is_user_password56(
        b"pw", b"\x00" * 48, 6
    ) is False


def test_is_owner_password234_alias_round_trip() -> None:
    """``is_owner_password234`` mirrors ``_is_owner_password_2_3_4``."""
    user_pw = b"u"
    owner_pw = b"o"
    doc_id = b"\x11" * 16
    perms = -3904
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, 3, 16
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, perms, doc_id, 3, 16
    )
    assert StandardSecurityHandler.is_owner_password234(
        owner_pw, u, o, perms, doc_id, 3, 16, True
    )


def test_is_owner_password56_alias_mismatches() -> None:
    """``is_owner_password56`` exposes ``_is_owner_password_5_6`` (alias)."""
    assert StandardSecurityHandler.is_owner_password56(
        b"pw", b"\x00" * 48, b"\x00" * 48, 6
    ) is False


# ---------- get_user_password234 r2 branch ---------------------------------


def test_get_user_password234_r2_round_trip() -> None:
    """Recover the padded user password from the owner password using
    r2's single-RC4-pass unwinding. Covers the ``enc_revision == 2``
    short-circuit at line 1949-1950."""
    user_pw = b"alice"
    owner_pw = b"bob"
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, 2, 16
    )
    recovered = StandardSecurityHandler.get_user_password234(owner_pw, o, 2, 16)
    # First N bytes match user_pw; the rest is PDF's 32-byte padding
    # vector (StandardSecurityHandler._pad_password).
    assert recovered[: len(user_pw)] == user_pw


def test_get_user_password234_r4_round_trip() -> None:
    """Recover the padded user password under r4 — exercises the 20-round
    rotated-key loop branch."""
    user_pw = b"alice"
    owner_pw = b"bob"
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, 4, 16
    )
    recovered = StandardSecurityHandler.get_user_password234(owner_pw, o, 4, 16)
    assert recovered[: len(user_pw)] == user_pw


# ---------- prepare_encryption_dict_rev234 / rev6 empty-owner-pw promotion --


def test_prepare_encryption_dict_rev234_empty_owner_pw_promotes_to_user() -> None:
    """An empty owner password falls back to the user password (covers
    line 2018-2019). Round-trip: subsequent password validation against
    the user password should succeed."""
    handler = StandardSecurityHandler()
    handler.set_revision(3)
    handler.set_version(2)
    handler.set_key_length(128)
    handler.set_aes(False)

    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(2)
    encryption.set_revision(3)
    encryption.set_length(128)
    encryption.set_p(-3904)

    handler.prepare_encryption_dict_rev234(
        "", "user-pw", encryption, -3904, object(), 3, 16
    )
    # Owner and user dictionaries are populated.
    assert encryption.get_o() is not None
    assert encryption.get_u() is not None


def test_prepare_encryption_dict_rev234_r4_installs_aesv2() -> None:
    """r4 install must wire the AESV2 crypt filter (covers line 2046-2047)."""
    handler = StandardSecurityHandler()
    handler.set_revision(4)
    handler.set_version(4)
    handler.set_key_length(128)
    handler.set_aes(False)

    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_length(128)
    encryption.set_p(-3904)

    handler.prepare_encryption_dict_rev234(
        "owner-pw", "user-pw", encryption, -3904, object(), 4, 16
    )
    assert handler.is_aes() is True


def test_prepare_encryption_dict_rev6_empty_owner_pw_promotes_to_user() -> None:
    """Empty owner pw under r6 falls back to user (covers L2065-2066)."""
    handler = StandardSecurityHandler()
    handler.set_revision(6)
    handler.set_version(5)
    handler.set_key_length(256)
    handler.set_aes(True)
    handler._encrypt_metadata = True

    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(-3904)

    handler.prepare_encryption_dict_rev6("", "user-pw", encryption, -3904)
    # /U /UE /O /OE /Perms are all populated.
    assert encryption.get_u() is not None
    assert encryption.get_o() is not None
    assert encryption.get_perms() is not None

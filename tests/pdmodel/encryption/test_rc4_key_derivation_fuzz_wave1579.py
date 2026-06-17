"""Fuzz + parity tests for the RC4-era standard-security-handler key derivation.

Hammers ``StandardSecurityHandler`` Algorithm 2 (encryption key), Algorithm 3
(/O entry), Algorithm 4/5 (/U entry), Algorithm 6 (user auth) and Algorithm 7
(owner auth) for revisions 2, 3 and 4 against a fully independent reference
implementation inlined below. The reference deliberately re-derives every
constant from PDF 32000-1 §7.6.4 (the 32-byte padding, the P-as-little-endian
signed-int32 mix, the 50 truncated MD5 rounds for R>=3, the 19 XOR-key RC4
rounds, the EncryptMetadata 0xFFFFFFFF gate for R4) so a divergence in the
production code surfaces as a byte mismatch rather than both sides sharing a bug.

Wave 1579 (Agent D).
"""

from __future__ import annotations

import hashlib
import struct

import pytest

from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)

# ----------------------------------------------------------------------------
# Independent reference implementation (NOT importing any production helper).
# ----------------------------------------------------------------------------

_PAD = bytes(
    [
        0x28, 0xBF, 0x4E, 0x5E, 0x4E, 0x75, 0x8A, 0x41,
        0x64, 0x00, 0x4E, 0x56, 0xFF, 0xFA, 0x01, 0x08,
        0x2E, 0x2E, 0x00, 0xB6, 0xD0, 0x68, 0x3E, 0x80,
        0x2F, 0x0C, 0xA9, 0xFE, 0x64, 0x53, 0x69, 0x7A,
    ]
)


def _ref_rc4(key: bytes, data: bytes) -> bytes:
    """Textbook RC4 — independent of cryptography's ARC4."""
    s = list(range(256))
    j = 0
    klen = len(key)
    for i in range(256):
        j = (j + s[i] + key[i % klen]) & 0xFF
        s[i], s[j] = s[j], s[i]
    out = bytearray(len(data))
    i = j = 0
    for n, ch in enumerate(data):
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out[n] = ch ^ s[(s[i] + s[j]) & 0xFF]
    return bytes(out)


def _ref_pad(password: bytes) -> bytes:
    password = password[:32]
    return password + _PAD[: 32 - len(password)]


def _ref_p_le(permissions: int) -> bytes:
    v = permissions & 0xFFFFFFFF
    if v & 0x80000000:
        v -= 0x100000000
    return struct.pack("<i", v)


def _ref_enc_key(
    password: bytes,
    o: bytes,
    permissions: int,
    document_id: bytes,
    revision: int,
    key_len: int,
    encrypt_metadata: bool,
) -> bytes:
    """Algorithm 2."""
    h = hashlib.md5(usedforsecurity=False)
    h.update(_ref_pad(password))
    h.update(o)
    h.update(_ref_p_le(permissions))
    h.update(document_id)
    if revision == 4 and not encrypt_metadata:
        h.update(b"\xff\xff\xff\xff")
    digest = h.digest()
    if revision in (3, 4):
        for _ in range(50):
            digest = hashlib.md5(digest[:key_len], usedforsecurity=False).digest()
    return digest[:key_len]


def _ref_o_value(
    owner_password: bytes,
    user_password: bytes,
    revision: int,
    key_len: int,
) -> bytes:
    """Algorithm 3."""
    digest = hashlib.md5(_ref_pad(owner_password), usedforsecurity=False).digest()
    if revision >= 3:
        for _ in range(50):
            digest = hashlib.md5(digest[:key_len], usedforsecurity=False).digest()
    rc4_key = digest[:key_len]
    result = _ref_rc4(rc4_key, _ref_pad(user_password))
    if revision >= 3:
        for i in range(1, 20):
            result = _ref_rc4(bytes(b ^ i for b in rc4_key), result)
    return result


def _ref_u_value(
    user_password: bytes,
    o: bytes,
    permissions: int,
    document_id: bytes,
    revision: int,
    key_len: int,
    encrypt_metadata: bool,
) -> bytes:
    """Algorithm 4 (R2) / Algorithm 5 (R3+)."""
    file_key = _ref_enc_key(
        user_password, o, permissions, document_id, revision, key_len, encrypt_metadata
    )
    if revision == 2:
        return _ref_rc4(file_key, _PAD)
    h = hashlib.md5(usedforsecurity=False)
    h.update(_PAD)
    h.update(document_id)
    result = _ref_rc4(file_key, h.digest())
    for i in range(1, 20):
        result = _ref_rc4(bytes(b ^ i for b in file_key), result)
    return result + b"\x00" * (32 - len(result))


# ----------------------------------------------------------------------------
# Test vectors — (revision, key_len_bytes, encrypt_metadata)
# ----------------------------------------------------------------------------

_R2 = (2, 5, True)
_R3 = (3, 16, True)
_R4 = (4, 16, True)
_R4_NOMETA = (4, 16, False)
_R3_40 = (3, 5, True)  # 40-bit key under R3 (truncation matters here)

_PROFILES = [_R2, _R3, _R4, _R4_NOMETA, _R3_40]
_PROFILE_IDS = ["r2_40", "r3_128", "r4_128", "r4_128_nometa", "r3_40"]

_PASSWORDS = [b"", b"a", b"secret", b"owner-pw-1234567890", b"\x00\x01\xff", _PAD, _PAD + b"x"]
_IDS = [b"", b"\x00" * 16, b"0123456789abcdef", bytes(range(16))]
_PERMS = [-1, -3904, 0, 0xFFFFFFFC, -44, 0x7FFFFFFF]


# ----------------------------------------------------------------------------
# Algorithm 2 — file encryption key
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("profile", _PROFILES, ids=_PROFILE_IDS)
@pytest.mark.parametrize("pw", _PASSWORDS, ids=[f"pw{i}" for i in range(len(_PASSWORDS))])
@pytest.mark.parametrize("doc_id", _IDS, ids=[f"id{i}" for i in range(len(_IDS))])
def test_enc_key_matches_reference(profile, pw, doc_id):
    revision, key_len, enc_meta = profile
    o = bytes(range(32))  # arbitrary fixed /O
    perms = -3904
    expected = _ref_enc_key(pw, o, perms, doc_id, revision, key_len, enc_meta)
    got = StandardSecurityHandler._compute_encryption_key(
        pw, o, perms, doc_id, revision, key_len, enc_meta
    )
    assert got == expected
    assert len(got) == key_len


@pytest.mark.parametrize("perms", _PERMS, ids=[f"p{i}" for i in range(len(_PERMS))])
def test_enc_key_permissions_little_endian_signed(perms):
    # The P mix must be 4-byte little-endian *signed* int32 — a big-endian or
    # unsigned encoding diverges for high-bit-set permission values.
    o = bytes(range(32))
    doc_id = b"0123456789abcdef"
    expected = _ref_enc_key(b"pw", o, perms, doc_id, 4, 16, True)
    got = StandardSecurityHandler._compute_encryption_key(
        b"pw", o, perms, doc_id, 4, 16, True
    )
    assert got == expected


def test_enc_key_r4_metadata_flag_changes_key():
    o = bytes(range(32))
    doc_id = b"0123456789abcdef"
    with_meta = StandardSecurityHandler._compute_encryption_key(
        b"pw", o, -44, doc_id, 4, 16, True
    )
    without_meta = StandardSecurityHandler._compute_encryption_key(
        b"pw", o, -44, doc_id, 4, 16, False
    )
    assert with_meta != without_meta
    assert without_meta == _ref_enc_key(b"pw", o, -44, doc_id, 4, 16, False)


def test_enc_key_r3_metadata_flag_ignored():
    # The 0xFFFFFFFF mix is gated on revision == 4 ONLY; R3 must ignore the flag.
    o = bytes(range(32))
    doc_id = b"0123456789abcdef"
    a = StandardSecurityHandler._compute_encryption_key(b"pw", o, -44, doc_id, 3, 16, True)
    b = StandardSecurityHandler._compute_encryption_key(b"pw", o, -44, doc_id, 3, 16, False)
    assert a == b


def test_enc_key_50_round_truncation_r3_40bit():
    # With a 5-byte key under R3 the 50 rounds must re-hash only the first 5
    # bytes of each digest. A full-16-byte re-hash would produce a different key.
    o = bytes(range(32))
    doc_id = b"id"
    got = StandardSecurityHandler._compute_encryption_key(b"pw", o, -3904, doc_id, 3, 5, True)
    assert got == _ref_enc_key(b"pw", o, -3904, doc_id, 3, 5, True)
    # Sanity: a wrong (full-digest) re-hash differs from the truncated one.
    h = hashlib.md5(usedforsecurity=False)
    h.update(_ref_pad(b"pw"))
    h.update(o)
    h.update(_ref_p_le(-3904))
    h.update(doc_id)
    digest = h.digest()
    for _ in range(50):
        digest = hashlib.md5(digest, usedforsecurity=False).digest()  # full, wrong
    assert got != digest[:5]


# ----------------------------------------------------------------------------
# Algorithm 3 — /O entry
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("profile", _PROFILES, ids=_PROFILE_IDS)
@pytest.mark.parametrize("owner_pw", _PASSWORDS, ids=[f"o{i}" for i in range(len(_PASSWORDS))])
def test_o_value_matches_reference(profile, owner_pw):
    revision, key_len, _ = profile
    user_pw = b"user-pass"
    expected = _ref_o_value(owner_pw, user_pw, revision, key_len)
    got = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, revision, key_len
    )
    assert got == expected
    assert len(got) == 32


def test_o_value_19_xor_rounds_r3():
    # R3+ runs 19 extra RC4 rounds with key byte ^ i (i = 1..19). A wrong
    # iteration count or wrong XOR would diverge.
    owner_pw, user_pw = b"theowner", b"theuser"
    got = StandardSecurityHandler._compute_owner_password_r2_r4(owner_pw, user_pw, 3, 16)
    # Reconstruct with the 19-round XOR loop omitted -> must differ.
    digest = hashlib.md5(_ref_pad(owner_pw), usedforsecurity=False).digest()
    for _ in range(50):
        digest = hashlib.md5(digest[:16], usedforsecurity=False).digest()
    rc4_key = digest[:16]
    no_rounds = _ref_rc4(rc4_key, _ref_pad(user_pw))
    assert got != no_rounds
    assert got == _ref_o_value(owner_pw, user_pw, 3, 16)


def test_o_value_r2_single_rc4():
    # R2 = a single RC4 pass, no 50-round, no 19-round.
    got = StandardSecurityHandler._compute_owner_password_r2_r4(b"o", b"u", 2, 5)
    rc4_key = hashlib.md5(_ref_pad(b"o"), usedforsecurity=False).digest()[:5]
    assert got == _ref_rc4(rc4_key, _ref_pad(b"u"))


# ----------------------------------------------------------------------------
# Algorithm 4/5 — /U entry
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("profile", _PROFILES, ids=_PROFILE_IDS)
@pytest.mark.parametrize("doc_id", _IDS, ids=[f"id{i}" for i in range(len(_IDS))])
def test_u_value_matches_reference(profile, doc_id):
    revision, key_len, enc_meta = profile
    user_pw = b"the-user"
    o = _ref_o_value(b"the-owner", user_pw, revision, key_len)
    expected = _ref_u_value(user_pw, o, -3904, doc_id, revision, key_len, enc_meta)
    got = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, -3904, doc_id, revision, key_len, encrypt_metadata=enc_meta
    )
    assert got == expected
    assert len(got) == 32


def test_u_value_r2_vs_r3_path_distinct():
    # R2 = RC4(file_key, pad); R3+ = MD5(pad+ID) then 20 RC4 rounds. The two
    # paths must not collide.
    user_pw, o, doc_id = b"u", bytes(range(32)), b"0123456789abcdef"
    u_r2 = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, -3904, doc_id, 2, 5, encrypt_metadata=True
    )
    u_r3 = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, -3904, doc_id, 3, 16, encrypt_metadata=True
    )
    assert u_r2 == _ref_rc4(
        _ref_enc_key(user_pw, o, -3904, doc_id, 2, 5, True), _PAD
    )
    assert u_r3 != u_r2


# ----------------------------------------------------------------------------
# Algorithm 6 / 7 — authentication round-trips
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("profile", _PROFILES, ids=_PROFILE_IDS)
def test_user_auth_roundtrip(profile):
    revision, key_len, enc_meta = profile
    user_pw, owner_pw = b"user-secret", b"owner-secret"
    doc_id = b"0123456789abcdef"
    perms = -3904
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, revision, key_len
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, perms, doc_id, revision, key_len, encrypt_metadata=enc_meta
    )
    # Correct user password authenticates.
    assert StandardSecurityHandler.is_user_password(
        user_pw, u, o, perms, doc_id, revision, key_len, enc_meta
    )
    # Wrong password rejected.
    assert not StandardSecurityHandler.is_user_password(
        b"wrong", u, o, perms, doc_id, revision, key_len, enc_meta
    )


@pytest.mark.parametrize("profile", _PROFILES, ids=_PROFILE_IDS)
def test_owner_auth_roundtrip(profile):
    revision, key_len, enc_meta = profile
    user_pw, owner_pw = b"user-secret", b"owner-secret"
    doc_id = b"0123456789abcdef"
    perms = -3904
    o = StandardSecurityHandler._compute_owner_password_r2_r4(
        owner_pw, user_pw, revision, key_len
    )
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        user_pw, o, perms, doc_id, revision, key_len, encrypt_metadata=enc_meta
    )
    assert StandardSecurityHandler.is_owner_password(
        owner_pw, u, o, perms, doc_id, revision, key_len, enc_meta
    )
    assert not StandardSecurityHandler.is_owner_password(
        b"not-the-owner", u, o, perms, doc_id, revision, key_len, enc_meta
    )


def test_owner_recovers_user_password():
    # Algorithm 7: owner password recovers the (padded) user password.
    user_pw, owner_pw = b"realuser", b"realowner"
    o = StandardSecurityHandler._compute_owner_password_r2_r4(owner_pw, user_pw, 3, 16)
    recovered = StandardSecurityHandler.get_user_password(owner_pw, o, 3, 16)
    assert recovered[: len(user_pw)] == user_pw


def test_owner_equals_user_when_no_owner_password():
    # When owner == user the user password should still authenticate as user.
    pw = b"sharedpw"
    doc_id = b"0123456789abcdef"
    o = StandardSecurityHandler._compute_owner_password_r2_r4(pw, pw, 4, 16)
    u = StandardSecurityHandler._compute_user_password_r2_r4(
        pw, o, -3904, doc_id, 4, 16, encrypt_metadata=True
    )
    assert StandardSecurityHandler.is_user_password(
        pw, u, o, -3904, doc_id, 4, 16, True
    )


def test_pad_password_exact_32_bytes():
    # Algorithm 2 step (a): empty -> full padding; >=32 -> truncated to 32.
    assert StandardSecurityHandler._pad_password(b"") == _PAD
    assert StandardSecurityHandler._pad_password(b"ab") == b"ab" + _PAD[:30]
    long = bytes(range(40))
    assert StandardSecurityHandler._pad_password(long) == long[:32]
    assert len(StandardSecurityHandler._pad_password(b"x")) == 32


def test_o_value_r2_key_length_guard():
    # compute_owner_password raises for R2 with key length != 5 (Java L920).
    with pytest.raises(OSError):
        StandardSecurityHandler.compute_owner_password(b"o", b"u", 2, 16)
    # R2 with len 5 is fine.
    StandardSecurityHandler.compute_owner_password(b"o", b"u", 2, 5)

"""Fuzz + parity coverage for the PDF 2.0 / R6 (AESV3) password hash.

Targets ISO 32000-2 §7.6.4.3.4 Algorithm 2.B as implemented by
``StandardSecurityHandler._compute_hash_r5_r6`` / ``compute_hash_2b`` /
``compute_hash_2a``.

Strategy: an inlined, independent reference implementation of Algorithm 2.B
(written from the spec text, *not* derived from the production code) is the
oracle. It deliberately uses the literal spec constructs the production code
optimises away:

  * the mod-3 selection via ``int.from_bytes(e[:16], "big") % 3`` (the
    production code sums the 16 bytes mod 3 — equivalent only because
    ``256 ≡ 1 (mod 3)``);
  * the last-byte termination compare via ``e[-1] & 0xFF`` (unsigned);
  * the >= 64-round-minimum then "continue while last byte of E > round - 32".

If the production code ever drifts on round count (63 vs 64), termination
offset (< vs <=, round-32), the SHA-256/384/512 mod-3 mapping, the AES
key/iv split, the K1 repetition count, or the user-key concatenation, these
cases diverge from the independent reference.
"""

from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler as SSH,
)


# --------------------------------------------------------------------------- #
# Independent reference implementation of Algorithm 2.B (oracle).             #
# --------------------------------------------------------------------------- #
def _reference_hash_2b(
    input_data: bytes, password: bytes, user_key: bytes | None
) -> bytes:
    """Spec-literal Algorithm 2.B. Returns the 32-byte hardened hash."""
    k = hashlib.sha256(input_data).digest()
    uk = b""
    if user_key is not None and len(user_key) >= 48:
        uk = bytes(user_key[:48])

    e = b""
    round_no = 0
    # Algorithm 2.B: run at least 64 rounds, then keep going while the last
    # byte of E (unsigned) is greater than round_no - 32.
    while round_no < 64 or (e[-1] & 0xFF) > round_no - 32:
        k1 = (password + k + uk) * 64
        aes_key = k[:16]
        iv = k[16:32]
        encryptor = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).encryptor()
        e = encryptor.update(k1) + encryptor.finalize()
        remainder = int.from_bytes(e[:16], "big") % 3
        if remainder == 0:
            k = hashlib.sha256(e).digest()
        elif remainder == 1:
            k = hashlib.sha384(e).digest()
        else:
            k = hashlib.sha512(e).digest()
        round_no += 1
    return k[:32]


def _prod(input_data: bytes, password: bytes, user_key: bytes | None) -> bytes:
    return SSH._compute_hash_r5_r6(  # noqa: SLF001
        bytes(input_data),
        bytes(password),
        bytes(user_key) if user_key is not None else b"",
        6,
    )


# --------------------------------------------------------------------------- #
# 1. Random fuzz: production vs independent reference.                        #
# --------------------------------------------------------------------------- #
def _lcg(seed: int):
    state = seed & 0xFFFFFFFF
    while True:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        yield state


def _rand_bytes(gen, n: int) -> bytes:
    return bytes(next(gen) & 0xFF for _ in range(n))


@pytest.mark.parametrize("seed", list(range(24)))
def test_fuzz_prod_matches_reference(seed: int) -> None:
    gen = _lcg(seed * 2654435761 + 1)
    pw_len = next(gen) % 24
    salt_len = 8
    uk_choice = next(gen) % 3  # 0 -> empty, 1 -> short(<48), 2 -> 48-byte
    password = _rand_bytes(gen, pw_len)
    salt = _rand_bytes(gen, salt_len)
    if uk_choice == 0:
        user_key: bytes = b""
    elif uk_choice == 1:
        user_key = _rand_bytes(gen, next(gen) % 47)
    else:
        user_key = _rand_bytes(gen, 48)
    input_data = password + salt + user_key

    expected = _reference_hash_2b(input_data, password, user_key)
    got = _prod(input_data, password, user_key)
    assert got == expected
    assert len(got) == 32


# --------------------------------------------------------------------------- #
# 2. compute_hash_2b public alias parity with the private routine + ref.      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("password", "salt", "uk"),
    [
        (b"", b"\x00" * 8, b""),
        (b"secret", b"\x01\x02\x03\x04\x05\x06\x07\x08", b""),
        (b"x" * 127, b"\xaa" * 8, b""),
        (b"owner-pass", b"\x10\x20\x30\x40\x50\x60\x70\x80", b"\x00" * 48),
        (b"\xff\xfe\xfd", b"\x99" * 8, bytes(range(48))),
    ],
    ids=["empty", "secret", "len127", "owner48", "binary"],
)
def test_compute_hash_2b_alias_matches_reference(
    password: bytes, salt: bytes, uk: bytes
) -> None:
    input_data = password + salt + uk
    expected = _reference_hash_2b(input_data, password, uk)
    got = SSH.compute_hash_2b(input_data, password, uk if uk else None)
    assert got == expected
    assert len(got) == 32


# --------------------------------------------------------------------------- #
# 3. mod-3 selection: byte-sum mod 3 must equal big-endian-integer mod 3.     #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seed", list(range(12)))
def test_mod3_byte_sum_equals_bigendian_mod3(seed: int) -> None:
    """The production code selects SHA-256/384/512 by summing the first 16
    bytes of E mod 3; the spec says treat them as a big-endian integer mod 3.
    These agree only because 256 ≡ 1 (mod 3). Assert it holds for arbitrary
    16-byte blocks so a future 'optimisation' can't silently break it."""
    gen = _lcg(seed * 40503 + 7)
    block = _rand_bytes(gen, 16)
    assert (sum(block) % 3) == (int.from_bytes(block, "big") % 3)


# --------------------------------------------------------------------------- #
# 4. Round termination: at least 64 rounds, then last-byte <= round-32 stops. #
# --------------------------------------------------------------------------- #
def _count_rounds(input_data: bytes, password: bytes, user_key: bytes) -> int:
    k = hashlib.sha256(input_data).digest()
    uk = b""
    if user_key and len(user_key) >= 48:
        uk = bytes(user_key[:48])
    e = b""
    round_no = 0
    while round_no < 64 or (e[-1] & 0xFF) > round_no - 32:
        k1 = (password + k + uk) * 64
        enc = Cipher(algorithms.AES(k[:16]), modes.CBC(k[16:32])).encryptor()
        e = enc.update(k1) + enc.finalize()
        rem = int.from_bytes(e[:16], "big") % 3
        k = (hashlib.sha256, hashlib.sha384, hashlib.sha512)[rem](e).digest()
        round_no += 1
    return round_no


@pytest.mark.parametrize("seed", list(range(10)))
def test_round_count_is_at_least_64(seed: int) -> None:
    gen = _lcg(seed * 7919 + 3)
    password = _rand_bytes(gen, next(gen) % 20)
    salt = _rand_bytes(gen, 8)
    rounds = _count_rounds(password + salt, password, b"")
    assert rounds >= 64
    # And the production output for that input matches the reference, proving
    # the production loop ran the same number of rounds.
    assert _prod(password + salt, password, b"") == _reference_hash_2b(
        password + salt, password, b""
    )


def test_termination_uses_unsigned_last_byte() -> None:
    """The compare must use the *unsigned* last byte of E. A signed compare
    (Java byte is signed) would terminate early for E[-1] >= 0x80. The
    reference uses ``& 0xFF``; production must agree across many inputs that
    statistically include high last bytes."""
    for seed in range(40):
        gen = _lcg(seed * 100003 + 11)
        password = _rand_bytes(gen, next(gen) % 16)
        salt = _rand_bytes(gen, 8)
        assert _prod(password + salt, password, b"") == _reference_hash_2b(
            password + salt, password, b""
        )


# --------------------------------------------------------------------------- #
# 5. User-password path (udata empty) vs owner-password path (udata = U).     #
# --------------------------------------------------------------------------- #
def test_user_path_vs_owner_path_differ() -> None:
    """Owner-password hashing folds the 48-byte /U into every round; the user
    path uses no udata. Same password+salt must give different hashes."""
    password = b"the-password"
    salt = b"\x11\x22\x33\x44\x55\x66\x77\x88"
    u_entry = bytes(range(48))
    user_path = _prod(password + salt, password, b"")
    owner_path = _prod(password + salt + u_entry, password, u_entry)
    assert user_path != owner_path
    assert user_path == _reference_hash_2b(password + salt, password, b"")
    assert owner_path == _reference_hash_2b(
        password + salt + u_entry, password, u_entry
    )


def test_user_key_shorter_than_48_ignored_like_empty() -> None:
    """A < 48-byte user_key is excluded from the per-round block (PDFBox
    ``computeHash2B``). It must hash identically to ``b''``."""
    password = b"pw"
    salt = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    base = password + salt
    h_empty = _prod(base, password, b"")
    for short_len in (1, 16, 32, 47):
        gen = _lcg(short_len * 31 + 5)
        short = _rand_bytes(gen, short_len)
        assert _prod(base, password, short) == h_empty


def test_user_key_exactly_48_changes_hash() -> None:
    password = b"pw"
    salt = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    base = password + salt
    full = bytes(range(48))
    assert _prod(base + full, password, full) != _prod(base, password, b"")


# --------------------------------------------------------------------------- #
# 6. Empty password.                                                          #
# --------------------------------------------------------------------------- #
def test_empty_password_matches_reference() -> None:
    salt = b"\x00\x01\x02\x03\x04\x05\x06\x07"
    assert _prod(salt, b"", b"") == _reference_hash_2b(salt, b"", b"")


# --------------------------------------------------------------------------- #
# 7. Unicode / SASLprep password bytes flow into the same hash.              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "password_str",
    ["пароль", "naïve", "日本語", "ﬁle", "a b c"],
    ids=["cyrillic", "accent", "cjk", "ligature", "spaces"],
)
def test_unicode_password_bytes_hash_deterministically(password_str: str) -> None:
    pw_bytes = password_str.encode("utf-8")
    salt = b"\x42" * 8
    h1 = _prod(pw_bytes + salt, pw_bytes, b"")
    h2 = _prod(pw_bytes + salt, pw_bytes, b"")
    assert h1 == h2 == _reference_hash_2b(pw_bytes + salt, pw_bytes, b"")
    assert len(h1) == 32


# --------------------------------------------------------------------------- #
# 8. compute_hash_2a (Algorithm 2.A) wires truncation + adjust_user_key.      #
# --------------------------------------------------------------------------- #
def test_compute_hash_2a_user_path() -> None:
    password = b"user-pw"
    salt = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    truncated = SSH.truncate_127(password)
    expected = _reference_hash_2b(truncated + salt, truncated, b"")
    assert SSH.compute_hash_2a(password, salt, b"") == expected


def test_compute_hash_2a_owner_path_includes_u() -> None:
    password = b"owner-pw"
    salt = b"\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10"
    u_entry = bytes(range(48))
    truncated = SSH.truncate_127(password)
    expected = _reference_hash_2b(
        truncated + salt + u_entry, truncated, u_entry
    )
    assert SSH.compute_hash_2a(password, salt, u_entry) == expected


def test_compute_hash_2a_truncates_password_at_127() -> None:
    """Passwords beyond 127 bytes are truncated before hashing (truncate127);
    a 200-byte and its 127-byte prefix must produce the same 2.A hash."""
    salt = b"\xab" * 8
    long_pw = bytes((i % 251) + 1 for i in range(200))
    assert SSH.compute_hash_2a(long_pw, salt, b"") == SSH.compute_hash_2a(
        long_pw[:127], salt, b""
    )


# --------------------------------------------------------------------------- #
# 9. r5 path is plain SHA-256 (no AES rounds) — guards the revision switch.   #
# --------------------------------------------------------------------------- #
def test_r5_is_plain_sha256_no_rounds() -> None:
    password = b"pw"
    salt = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    data = password + salt
    got = SSH._compute_hash_r5_r6(data, password, b"", 5)  # noqa: SLF001
    assert got == hashlib.sha256(data).digest()
    # r6 over the same input must differ (it applies the hardened rounds).
    assert got != _prod(data, password, b"")


# --------------------------------------------------------------------------- #
# 10. Determinism / stability across repeated calls.                          #
# --------------------------------------------------------------------------- #
def test_repeated_calls_are_stable() -> None:
    password = b"repeat"
    salt = b"\x55" * 8
    first = _prod(password + salt, password, b"")
    for _ in range(5):
        assert _prod(password + salt, password, b"") == first

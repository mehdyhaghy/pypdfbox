"""Wave 1369 — eexec cipher (Adobe Type 1 spec §7) parity tests.

Type 1 eexec is NOT standard RC4. It is the Adobe-defined LCG stream
cipher with constants ``c1 = 52845``, ``c2 = 22719``, seed ``55665``
and a 4-byte random salt prepended to the plaintext on encryption.

The recurrence is::

    cipher = plain ^ (R >> 8)
    R      = ((cipher + R) * c1 + c2) & 0xFFFF

This file exercises the cipher invariants directly: salt length, salt
randomness, the inverse relationship of encrypt/decrypt, and the
specific upstream-shaped ``Type1FontUtil.encrypt`` / ``.decrypt``
helpers that take an explicit seed.
"""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil

# ---------- 4-byte random salt ----------


def test_eexec_encrypt_prepends_4_byte_salt() -> None:
    plain = b"hello eexec"
    cipher = Type1FontUtil.eexec_encrypt(plain)
    # Salt + plaintext map to salt-len + plaintext-len ciphertext bytes.
    assert len(cipher) == len(plain) + 4


def test_eexec_encrypt_salt_is_random() -> None:
    # Encrypt the SAME plaintext twice. The 4-byte salt should make the
    # ciphertexts differ. (Probability of collision is < 2^-32.)
    plain = b"deterministic plaintext"
    c1 = Type1FontUtil.eexec_encrypt(plain)
    c2 = Type1FontUtil.eexec_encrypt(plain)
    assert c1 != c2
    # But both decrypt back to the original.
    assert Type1FontUtil.eexec_decrypt(c1) == plain
    assert Type1FontUtil.eexec_decrypt(c2) == plain


def test_eexec_round_trip_known_seed() -> None:
    # End-to-end inverse for a 256-byte payload covering every byte value.
    plain = bytes(range(256))
    assert Type1FontUtil.eexec_decrypt(Type1FontUtil.eexec_encrypt(plain)) == plain


# ---------- Upstream-parity static helpers ----------


def test_static_encrypt_uses_zero_prefix_not_random() -> None:
    # ``Type1FontUtil.encrypt`` mirrors upstream's static helper which
    # uses a zero-pad warm-up (not a random salt). The output must
    # therefore be deterministic across runs.
    out1 = Type1FontUtil.encrypt(b"abc", 55665, 4)
    out2 = Type1FontUtil.encrypt(b"abc", 55665, 4)
    assert out1 == out2
    assert len(out1) == 4 + 3


def test_static_encrypt_decrypt_round_trip_with_arbitrary_seed() -> None:
    # Seed 12345 is neither EEXEC_KEY nor CHARSTRING_KEY — proves the
    # cipher is parameterised cleanly.
    plain = b"interop seed exercise"
    cipher = Type1FontUtil.encrypt(plain, 12345, 4)
    recovered = Type1FontUtil.decrypt(cipher, 12345, 4)
    assert recovered == plain


def test_static_encrypt_rejects_negative_n() -> None:
    with pytest.raises(ValueError):
        Type1FontUtil.encrypt(b"x", 55665, -1)


# ---------- Salt length invariants ----------


@pytest.mark.parametrize(
    "n",
    [0, 1, 4, 8],
    ids=["n_zero", "n_one", "n_four", "n_eight"],
)
def test_charstring_round_trip_various_len_iv(n: int) -> None:
    # The cipher must round-trip cleanly for any non-negative warm-up
    # length. The CHARSTRING seed (4330) differs from the EEXEC seed
    # (55665) — using the wrong seed would corrupt the result.
    plain = b"\x01\x02\x03\x04hsbw\x80\x80\x80"
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=n)
    assert Type1FontUtil.charstring_decrypt(cipher, len_iv=n) == plain
    assert len(cipher) == len(plain) + n


def test_charstring_seed_differs_from_eexec_seed() -> None:
    # Decrypting eexec-ciphertext with the charstring decryptor MUST
    # NOT recover the plaintext (different seeds).
    plain = b"abcdefghijklmnopq"
    eexec = Type1FontUtil.eexec_encrypt(plain)
    cross = Type1FontUtil.charstring_decrypt(eexec, len_iv=4)
    assert cross != plain


# ---------- Known-answer test (zero-prefix, deterministic) ----------


def test_eexec_known_answer_zero_salt() -> None:
    # With the zero-pad ``encrypt`` helper we get a deterministic
    # ciphertext that locks in the exact cipher constants.
    # Plaintext is 4 NULs; seed = EEXEC_KEY (55665); n = 0.
    cipher = Type1FontUtil.encrypt(b"\x00\x00\x00\x00", 55665, 0)
    # Recompute the recurrence by hand: r0 = 55665.
    r = 55665
    expected = bytearray()
    for _ in range(4):
        c = (0 ^ (r >> 8)) & 0xFF
        expected.append(c)
        r = ((c + r) * 52845 + 22719) & 0xFFFF
    assert cipher == bytes(expected)


def test_static_decrypt_n_minus_one_passthrough() -> None:
    # ``Type1Parser.decrypt(data, r, -1)`` is upstream's documented
    # "no encryption" tolerance. The pypdfbox port keeps that quirk
    # in ``Type1Parser`` (not in Type1FontUtil) — verify it here so
    # any future refactor doesn't silently drop the escape hatch.
    from pypdfbox.fontbox.type1.type1_parser import Type1Parser

    raw = b"untouched"
    assert Type1Parser.decrypt(raw, 55665, -1) == raw

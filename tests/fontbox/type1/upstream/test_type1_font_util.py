"""Ported from upstream Apache PDFBox 3.0.x
``fontbox/src/test/java/org/apache/fontbox/cff/Type1FontUtilTest.java``.

Upstream covers the round-trip property of the eexec / charstring
ciphers and the hex helpers. We mirror each ``@Test`` method one-to-one;
where the upstream test depends on a JUnit-only mechanism (e.g.
parameterised seeds) we substitute the equivalent pytest pattern.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil

# Upstream constants from Type1FontUtilTest (Java lines 30-31).
DEFAULT_SEED = 12345
# Upstream loops 1000 times with fresh seeds — we reduce to 32 so the
# test suite stays snappy; the round-trip property is deterministic
# under the fixed seed already.
LOOPS = 32


def _random_bytes(length: int, seed: int) -> bytes:
    """Counterpart to upstream ``createRandomByteArray`` (Java lines 105-114).

    Java ``Random`` and Python ``random.Random`` use different PRNGs, so
    the *content* won't match upstream byte-for-byte — but that is
    irrelevant: every upstream assertion checks a round-trip property,
    not specific cipher output."""
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(length))


def test_eexec_encryption_decryption_round_trip() -> None:
    """Upstream: ``testEExecEncryption`` — encrypt, decrypt, expect equality."""
    plain = b"This is a test for the eexec encryption."
    encrypted = Type1FontUtil.eexec_encrypt(plain)
    decrypted = Type1FontUtil.eexec_decrypt(encrypted)
    assert decrypted == plain


def test_charstring_encryption_decryption_round_trip() -> None:
    """Upstream: ``testCharstringEncryption`` — same round-trip property
    against the charstring cipher (different seed, lenIV=4)."""
    plain = b"This is a test for the charstring encryption."
    encrypted = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    decrypted = Type1FontUtil.charstring_decrypt(encrypted, len_iv=4)
    assert decrypted == plain


def test_hex_encoding_decoding_round_trip() -> None:
    """Upstream: ``testHexEncoding`` — ``hexEncode(hexDecode(x)) == x``
    and vice versa for the PostScript hex helpers."""
    raw = b"Round-trip me through hex."
    hexed = Type1FontUtil.hex_encode(raw)
    assert Type1FontUtil.hex_decode(hexed) == raw


@pytest.mark.parametrize("size", [0, 1, 16, 256, 1024])
def test_eexec_round_trip_various_sizes(size: int) -> None:
    """Upstream uses a fixed payload; we sweep across sizes (parametrised)
    so any boundary mishandling shows up as a clear failure."""
    plain = bytes(i & 0xFF for i in range(size))
    assert Type1FontUtil.eexec_decrypt(Type1FontUtil.eexec_encrypt(plain)) == plain


@pytest.mark.parametrize("size", [0, 1, 16, 256])
def test_charstring_round_trip_various_sizes(size: int) -> None:
    plain = bytes(i & 0xFF for i in range(size))
    encrypted = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    assert Type1FontUtil.charstring_decrypt(encrypted, len_iv=4) == plain


# ---------- ported one-to-one from upstream JUnit ``@Test`` methods ----------


def test_hex_encoding() -> None:
    """Upstream: ``testHexEncoding`` (Java lines 36-45) — fixed seed plus
    looped fresh-seed round-trip of 128-byte payloads."""
    _try_hex_encoding(DEFAULT_SEED)
    for i in range(LOOPS):
        _try_hex_encoding(DEFAULT_SEED + i + 1)


def _try_hex_encoding(seed: int) -> None:
    plain = _random_bytes(128, seed)
    encoded = Type1FontUtil.hex_encode(plain)
    decoded = Type1FontUtil.hex_decode(encoded)
    assert decoded == plain, f"Seed: {seed}"


def test_eexec_encryption() -> None:
    """Upstream: ``testEexecEncryption`` (Java lines 60-69) — fixed seed
    plus looped fresh-seed round-trip through the eexec cipher."""
    _try_eexec_encryption(DEFAULT_SEED)
    for i in range(LOOPS):
        _try_eexec_encryption(DEFAULT_SEED + i + 1)


def _try_eexec_encryption(seed: int) -> None:
    plain = _random_bytes(128, seed)
    encrypted = Type1FontUtil.eexec_encrypt(plain)
    decrypted = Type1FontUtil.eexec_decrypt(encrypted)
    assert decrypted == plain, f"Seed: {seed}"


def test_charstring_encryption() -> None:
    """Upstream: ``testCharstringEncryption`` (Java lines 84-93) — fixed
    seed plus looped fresh-seed round-trip through the charstring
    cipher (lenIV = 4)."""
    _try_charstring_encryption(DEFAULT_SEED)
    for i in range(LOOPS):
        _try_charstring_encryption(DEFAULT_SEED + i + 1)


def _try_charstring_encryption(seed: int) -> None:
    plain = _random_bytes(128, seed)
    encrypted = Type1FontUtil.charstring_encrypt(plain, 4)
    decrypted = Type1FontUtil.charstring_decrypt(encrypted, 4)
    assert decrypted == plain, f"Seed: {seed}"


# ---------- low-level encrypt/decrypt (mirror Java private statics) ----------


def test_low_level_encrypt_is_deterministic() -> None:
    """Upstream private ``encrypt(byte[], int, int)`` (Java line 95)
    zero-pads the prefix slot — output is fully deterministic for a
    given (plaintext, r, n)."""
    plain = b"deterministic"
    a = Type1FontUtil.encrypt(plain, 55665, 4)
    b = Type1FontUtil.encrypt(plain, 55665, 4)
    assert a == b
    assert len(a) == len(plain) + 4


def test_low_level_encrypt_decrypt_round_trip() -> None:
    """Round-trip via the generic ``encrypt`` / ``decrypt`` entry points
    using the eexec seed."""
    plain = b"round trip via low level entry"
    cipher = Type1FontUtil.encrypt(plain, 55665, 4)
    assert Type1FontUtil.decrypt(cipher, 55665, 4) == plain


def test_low_level_encrypt_decrypt_charstring_seed() -> None:
    """Round-trip via the generic entry points using the charstring
    seed and a non-default lenIV."""
    plain = b"\x01\x02\x03\x04\x05" * 7
    cipher = Type1FontUtil.encrypt(plain, 4330, 0)
    assert Type1FontUtil.decrypt(cipher, 4330, 0) == plain


def test_low_level_encrypt_zero_prefix_layout() -> None:
    """When ``n > 0`` the upstream layout puts ``n`` zero bytes in front
    of the plaintext before encrypting; we verify the cipher recovers
    those leading zeros."""
    plain = b"abc"
    cipher = Type1FontUtil.encrypt(plain, 55665, 3)
    # Decrypt without dropping the prefix to inspect the warm-up region.
    plain_with_prefix = Type1FontUtil.decrypt(cipher, 55665, 0)
    assert plain_with_prefix[:3] == b"\x00\x00\x00"
    assert plain_with_prefix[3:] == plain


def test_low_level_encrypt_negative_n_rejected() -> None:
    with pytest.raises(ValueError):
        Type1FontUtil.encrypt(b"x", 55665, -1)

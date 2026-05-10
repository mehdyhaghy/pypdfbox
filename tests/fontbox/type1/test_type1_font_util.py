"""Hand-written tests for ``Type1FontUtil`` — the eexec / charstring
crypto helpers that mirror upstream ``org.apache.fontbox.type1.Type1FontUtil``.

The Adobe Type 1 stream cipher is a self-inverse pair: ``decrypt`` of
``encrypt`` is the identity. We verify that round-trip plus the
known-answer warm-up behaviour (eexec discards 4 bytes; charstring
discards ``lenIV`` bytes) plus the hex helpers used by the parser when
it normalises ASCII-form eexec.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil

# ---------- eexec round-trip ----------


def test_eexec_round_trip_short() -> None:
    plain = b"%!PS-AdobeFont-1.0: TestFont 001.000\n"
    cipher = Type1FontUtil.eexec_encrypt(plain)
    # First 4 bytes are random warm-up; total length grows by 4.
    assert len(cipher) == len(plain) + 4
    assert Type1FontUtil.eexec_decrypt(cipher) == plain


def test_eexec_round_trip_empty() -> None:
    cipher = Type1FontUtil.eexec_encrypt(b"")
    assert len(cipher) == 4  # only warm-up
    assert Type1FontUtil.eexec_decrypt(cipher) == b""


def test_eexec_round_trip_binary() -> None:
    plain = bytes(range(256)) * 8  # 2 KB of every byte value
    cipher = Type1FontUtil.eexec_encrypt(plain)
    assert Type1FontUtil.eexec_decrypt(cipher) == plain


def test_eexec_decrypt_rejects_short_input() -> None:
    with pytest.raises(ValueError, match="random prefix"):
        Type1FontUtil.eexec_decrypt(b"abc")  # < 4 bytes


def test_eexec_encryption_includes_random_prefix() -> None:
    """Two encryptions of the same plaintext should differ — the
    random prefix is freshly generated each time."""
    plain = b"hello world"
    a = Type1FontUtil.eexec_encrypt(plain)
    b = Type1FontUtil.eexec_encrypt(plain)
    # Tail content is determined by random prefix, so full equality is
    # astronomically unlikely.
    assert a != b
    assert Type1FontUtil.eexec_decrypt(a) == plain
    assert Type1FontUtil.eexec_decrypt(b) == plain


# ---------- charstring round-trip ----------


def test_charstring_round_trip_default_len_iv() -> None:
    plain = bytes(range(64))
    cipher = Type1FontUtil.charstring_encrypt(plain)
    assert len(cipher) == len(plain) + 4
    assert Type1FontUtil.charstring_decrypt(cipher) == plain


def test_charstring_round_trip_zero_len_iv() -> None:
    """Some private dicts set ``lenIV 0`` — no warm-up bytes."""
    plain = b"\x05\x06\x07\x08"
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=0)
    assert len(cipher) == len(plain)
    assert Type1FontUtil.charstring_decrypt(cipher, len_iv=0) == plain


def test_charstring_round_trip_long_len_iv() -> None:
    plain = b"\x99" * 32
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=8)
    assert len(cipher) == len(plain) + 8
    assert Type1FontUtil.charstring_decrypt(cipher, len_iv=8) == plain


def test_charstring_uses_different_seed_than_eexec() -> None:
    """Decrypting eexec-ciphertext with the charstring decoder must
    NOT recover the original plaintext (different seeds)."""
    plain = b"the quick brown fox"
    eexec_cipher = Type1FontUtil.eexec_encrypt(plain)
    # Charstring decrypt expects the same shape (4-byte prefix) so the
    # call won't error, but the result must differ from plain.
    wrong = Type1FontUtil.charstring_decrypt(eexec_cipher)
    assert wrong != plain


def test_negative_random_bytes_rejected() -> None:
    with pytest.raises(ValueError):
        Type1FontUtil.charstring_encrypt(b"x", len_iv=-1)
    with pytest.raises(ValueError):
        Type1FontUtil.charstring_decrypt(b"abcd", len_iv=-1)


# ---------- hex helpers ----------


def test_hex_encode_uppercase() -> None:
    assert Type1FontUtil.hex_encode(b"\x00\x10\xff") == "0010FF"


def test_hex_encode_round_trip() -> None:
    payload = bytes(range(256))
    assert Type1FontUtil.hex_decode(Type1FontUtil.hex_encode(payload)) == payload


def test_hex_decode_strips_whitespace() -> None:
    text = "DE AD\nBE\tEF"
    assert Type1FontUtil.hex_decode(text) == b"\xde\xad\xbe\xef"


def test_hex_decode_rejects_odd_length() -> None:
    with pytest.raises(ValueError, match="odd length"):
        Type1FontUtil.hex_decode("ABC")


def test_hex_decode_rejects_invalid_char() -> None:
    with pytest.raises(ValueError):
        Type1FontUtil.hex_decode("ZZ")

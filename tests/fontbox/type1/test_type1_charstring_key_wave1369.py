"""Wave 1369 — Type 1 charstring decryption with key 4330 + lenIV variants.

The charstring cipher shares the LCG recurrence with eexec but uses a
different seed (``4330``) and a font-supplied ``lenIV`` warm-up length
(default 4, sometimes 0 in fonts whose Private dict carries
``/lenIV 0 def``). These tests exercise the seed bias and the lenIV
parameterisation in isolation from the higher-level parser.
"""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import Type1Parser

# ---------- Charstring seed (4330) ----------


def test_charstring_decrypt_uses_seed_4330() -> None:
    # If the parser's static decrypt is called with CHARSTRING_KEY
    # and matches Type1FontUtil.charstring_decrypt with len_iv=4, the
    # constant is correct.
    plain = b"\x55\xaa\x10\x20\x30\x40\x80\x90"
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    via_parser = Type1Parser.decrypt(cipher, Type1Parser.CHARSTRING_KEY, 4)
    via_util = Type1FontUtil.charstring_decrypt(cipher, len_iv=4)
    assert via_parser == plain
    assert via_util == plain


def test_charstring_decrypt_rejects_seed_mismatch() -> None:
    # Seed 4329 (off by one) must produce garbage — proves the cipher
    # is seed-sensitive in the LCG sense, not just an XOR mask.
    plain = b"hsbw rmoveto endchar"
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    wrong = Type1Parser.decrypt(cipher, 4329, 4)
    assert wrong != plain


# ---------- lenIV variants ----------


@pytest.mark.parametrize(
    "len_iv",
    [0, 1, 2, 4, 8, 16],
    ids=["leniv_0", "leniv_1", "leniv_2", "leniv_4_default", "leniv_8", "leniv_16"],
)
def test_charstring_lenIV_round_trip(len_iv: int) -> None:
    plain = bytes(range(0, 32))  # spans a control / non-control mix
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=len_iv)
    assert Type1FontUtil.charstring_decrypt(cipher, len_iv=len_iv) == plain


def test_charstring_lenIV_zero_means_no_prefix() -> None:
    # /lenIV 0 def — common in highly-compressed fonts. The ciphertext
    # length matches the plaintext length exactly.
    plain = b"\x80\x90endchar"
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=0)
    assert len(cipher) == len(plain)
    assert Type1FontUtil.charstring_decrypt(cipher, len_iv=0) == plain


def test_charstring_lenIV_mismatch_loses_data() -> None:
    # Decrypting with the wrong lenIV drops too many or too few bytes.
    plain = b"the quick brown fox"
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    truncated = Type1FontUtil.charstring_decrypt(cipher, len_iv=6)
    # 6-byte trim of the 4-byte prefix output drops the first 2 plaintext bytes.
    assert truncated != plain
    assert len(truncated) == len(plain) - 2


# ---------- Static encrypt parity ----------


def test_static_encrypt_with_charstring_key_round_trips_via_parser_decrypt() -> None:
    # Mirror what ``Type1Parser.read_subrs`` does: encrypt with a
    # deterministic (zero-pad) prefix, then decrypt via the parser's
    # static helper which is the one called inline on parsed bytes.
    plain = b"\x0e"  # endchar
    cipher = Type1FontUtil.encrypt(plain, Type1Parser.CHARSTRING_KEY, 4)
    recovered = Type1Parser.decrypt(cipher, Type1Parser.CHARSTRING_KEY, 4)
    assert recovered == plain


# ---------- Edge cases ----------


def test_charstring_decrypt_empty_input_returns_empty() -> None:
    # Upstream's ``Type1Parser.decrypt`` returns empty bytes when the
    # ciphertext is empty regardless of n. Verify we match.
    assert Type1Parser.decrypt(b"", Type1Parser.CHARSTRING_KEY, 4) == b""


def test_charstring_decrypt_n_greater_than_input_returns_empty() -> None:
    # n > len(cipher) → upstream returns empty (the warm-up consumed
    # everything). Verify the same handling.
    assert Type1Parser.decrypt(b"\x01\x02", Type1Parser.CHARSTRING_KEY, 4) == b""


def test_charstring_encrypt_high_bytes_round_trip() -> None:
    # 0x80-0xFF byte range is the most fragile — make sure we don't
    # accidentally lose the high bit through a latin-1/utf-8 decode.
    plain = bytes(range(128, 256))
    cipher = Type1FontUtil.charstring_encrypt(plain, len_iv=4)
    assert Type1FontUtil.charstring_decrypt(cipher, len_iv=4) == plain

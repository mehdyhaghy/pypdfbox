"""Wave 1369 — Type1FontUtil binary-to-hex helpers and PFA hex eexec.

PFA (ASCII) Type 1 fonts present the eexec section as ASCII hex with
whitespace allowed between any pair of nibbles. ``Type1FontUtil``
exposes ``hex_encode`` and ``hex_decode`` for this normalisation,
matching upstream's commons-codec usage in ``Type1Parser.hexToBinary``.

These tests:

* lock in the upper-case + no-whitespace shape of ``hex_encode`` (PFA
  spec §7.2 recommends 80-char lines but only requires *some* hex);
* exercise ``hex_decode``'s whitespace stripping (space, tab, newline,
  carriage return) and its rejection of odd-length / non-hex input;
* round-trip every byte value 0x00..0xFF through encode/decode;
* cross-check the upstream-parity ``Type1Parser.hex_to_binary`` helper
  (which is the one called inline during PFA segment 2 parsing).
"""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import Type1Parser

# ---------- hex_encode shape ----------


def test_hex_encode_uppercase_and_no_whitespace() -> None:
    out = Type1FontUtil.hex_encode(b"\xab\xcd\xef")
    assert out == "ABCDEF"
    assert out.isupper()
    assert " " not in out and "\n" not in out


def test_hex_encode_empty_returns_empty_string() -> None:
    assert Type1FontUtil.hex_encode(b"") == ""


def test_hex_encode_accepts_bytearray() -> None:
    assert Type1FontUtil.hex_encode(bytearray(b"\x00\x80\xff")) == "0080FF"


# ---------- hex_decode whitespace handling ----------


@pytest.mark.parametrize(
    "encoded",
    ["DEAD BEEF", "DE AD BE EF", "DE\nAD\nBE\nEF", "DE\tAD\rBE\rEF", "DEADBEEF"],
    ids=["space", "every_byte", "newline", "mixed_ws", "no_ws"],
)
def test_hex_decode_strips_all_whitespace(encoded: str) -> None:
    assert Type1FontUtil.hex_decode(encoded) == b"\xde\xad\xbe\xef"


def test_hex_decode_mixed_case_input() -> None:
    # PFA producers sometimes lowercase the hex; upstream commons-codec
    # is case-insensitive. Lock that in.
    assert Type1FontUtil.hex_decode("deadbeef") == b"\xde\xad\xbe\xef"
    assert Type1FontUtil.hex_decode("DeAdBeEf") == b"\xde\xad\xbe\xef"


# ---------- hex_decode error paths ----------


def test_hex_decode_rejects_odd_length() -> None:
    with pytest.raises(ValueError, match="odd length"):
        Type1FontUtil.hex_decode("ABC")


def test_hex_decode_rejects_invalid_char() -> None:
    with pytest.raises(ValueError, match="invalid hex"):
        Type1FontUtil.hex_decode("ZZ")


# ---------- byte-level round-trip ----------


def test_hex_encode_decode_full_byte_range() -> None:
    every_byte = bytes(range(256))
    encoded = Type1FontUtil.hex_encode(every_byte)
    # 256 bytes -> 512 hex digits, no separators.
    assert len(encoded) == 512
    assert Type1FontUtil.hex_decode(encoded) == every_byte


# ---------- upstream-parity Type1Parser.hex_to_binary ----------


def test_parser_hex_to_binary_drops_unmatched_trailing_nibble() -> None:
    # Upstream allocates ``new byte[len / 2]`` — an odd nibble at the
    # end is silently dropped (integer division). pypdfbox mirrors this.
    assert Type1Parser.hex_to_binary(b"DEADBEE") == b"\xde\xad\xbe"


def test_parser_hex_to_binary_skips_non_hex_bytes() -> None:
    # The parser uses ``hex_to_binary`` on raw bytes from segment 2 — it
    # strips spaces and newlines but ALSO non-hex characters (since the
    # filter only retains hex digits).
    assert Type1Parser.hex_to_binary(b"DE AD/BE\nEF") == b"\xde\xad\xbe\xef"


def test_parser_hex_to_binary_empty_input_empty_output() -> None:
    assert Type1Parser.hex_to_binary(b"") == b""


def test_parser_is_binary_detects_ascii_hex_as_not_binary() -> None:
    # ``isBinary`` returns False when the first 4 bytes are all hex /
    # whitespace; this triggers the ``hex_to_binary`` normalise path
    # inside parse_binary.
    assert Type1Parser.is_binary(b"ABCD") is False
    assert Type1Parser.is_binary(b"01 23") is False
    # Any non-hex / non-space byte in the leading 4 flips to True.
    assert Type1Parser.is_binary(b"\x80\x90\xa0\xb0") is True


def test_parser_is_binary_short_input_treated_as_binary() -> None:
    # < 4 bytes — upstream defaults to "binary" (cannot make the
    # heuristic call); we mirror that.
    assert Type1Parser.is_binary(b"AB") is True
    assert Type1Parser.is_binary(b"") is True

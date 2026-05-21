"""Wave 1369 — Type 1 PFA vs PFB eexec section format detection.

Type 1 fonts come in two flavours:

* **PFA** (Printer Font ASCII) — the eexec body is ASCII hex with
  embedded whitespace allowed. The parser normalises it to raw bytes
  before running the LCG cipher.
* **PFB** (Printer Font Binary) — the eexec body is raw 8-bit
  ciphertext sliced out of segment 2 of the PFB record framing.

Upstream's heuristic (``Type1Parser.isBinary``) looks at the first 4
bytes: if at least one is not an ASCII hex digit or whitespace, the
body is treated as raw binary; otherwise it is decoded via
``hex_to_binary`` first.

These tests verify the dispatch in isolation: ASCII-hex round-trips,
mixed-whitespace round-trips, raw-binary passes through unchanged, and
the boundary (1st-byte distinguishes) is enforced. Note: ASCII85 is a
PostScript-level encoding (filter) but is NOT used for Type 1 eexec —
the spec only sanctions hex + binary, so the "ASCII85 vs Hex" lookout
in the wave brief reduces here to "ASCII-hex vs raw binary".
"""
from __future__ import annotations

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import Type1Parser

_HEADER = b"%!PS-AdobeFont-1.0: T 001.000\n6 dict begin\n/FontName /T def\n"
_PLAINTEXT = (
    b"dup /Private 5 dict dup begin\n/lenIV 4 def\n"
    b"/CharStrings 0 dict dup begin end\nend\n"
)


# ---------- raw binary dispatch ----------


def test_pfb_style_raw_binary_eexec() -> None:
    # ``eexec_encrypt`` returns raw bytes — at least one of the first
    # 4 will exceed ASCII hex range with overwhelming probability.
    binary_cipher = Type1FontUtil.eexec_encrypt(_PLAINTEXT)
    parser = Type1Parser()
    parser.parse(_HEADER, binary_cipher)
    assert parser.decrypted_binary == _PLAINTEXT


def test_is_binary_first_byte_outside_hex_triggers_binary() -> None:
    # First byte is 0x80 — not a hex digit, not whitespace. Treated as
    # raw binary; the parser does NOT hex-decode.
    cipher = b"\x80" + b"\x00" * 32
    assert Type1Parser.is_binary(cipher) is True


# ---------- ASCII-hex dispatch ----------


def test_pfa_style_ascii_hex_eexec_round_trip() -> None:
    binary_cipher = Type1FontUtil.eexec_encrypt(_PLAINTEXT)
    # Re-encode as ASCII hex without whitespace.
    hex_cipher = Type1FontUtil.hex_encode(binary_cipher).encode("ascii")
    parser = Type1Parser()
    parser.parse(_HEADER, hex_cipher)
    assert parser.decrypted_binary == _PLAINTEXT


def test_pfa_style_ascii_hex_with_whitespace_normalises_then_decrypts() -> None:
    binary_cipher = Type1FontUtil.eexec_encrypt(_PLAINTEXT)
    hex_no_ws = Type1FontUtil.hex_encode(binary_cipher)
    # Inject newlines every 64 chars (real PFA line wrap convention).
    chunks = [hex_no_ws[i:i + 64] for i in range(0, len(hex_no_ws), 64)]
    hex_with_ws = "\n".join(chunks).encode("ascii")
    parser = Type1Parser()
    parser.parse(_HEADER, hex_with_ws)
    assert parser.decrypted_binary == _PLAINTEXT


def test_pfa_lowercase_hex_round_trips() -> None:
    binary_cipher = Type1FontUtil.eexec_encrypt(_PLAINTEXT)
    hex_lower = Type1FontUtil.hex_encode(binary_cipher).lower().encode("ascii")
    parser = Type1Parser()
    parser.parse(_HEADER, hex_lower)
    assert parser.decrypted_binary == _PLAINTEXT


def test_is_binary_all_hex_first_four_means_not_binary() -> None:
    # 4 hex digits as the lead. is_binary -> False, parser will run
    # the hex_to_binary path.
    assert Type1Parser.is_binary(b"ABCD" + b"\x00" * 8) is False


def test_is_binary_hex_with_whitespace_lead_is_not_binary() -> None:
    # Whitespace is OK in the first 4 — still not binary.
    assert Type1Parser.is_binary(b"AB \nrest of the body") is False


# ---------- short input edge ----------


def test_is_binary_short_input_defaults_to_binary() -> None:
    # < 4 bytes — upstream defaults to binary (cannot make the call).
    assert Type1Parser.is_binary(b"") is True
    assert Type1Parser.is_binary(b"A") is True
    assert Type1Parser.is_binary(b"AB") is True
    assert Type1Parser.is_binary(b"ABC") is True


# ---------- ascii-hex truncation tolerance ----------


def test_ascii_hex_unmatched_trailing_nibble_dropped() -> None:
    # ``hex_to_binary`` drops the odd trailing nibble (upstream allocates
    # ``new byte[len/2]``). The parser must therefore handle ASCII hex
    # whose total nibble count is odd without raising.
    binary_cipher = Type1FontUtil.eexec_encrypt(_PLAINTEXT)
    hex_str = Type1FontUtil.hex_encode(binary_cipher) + "F"  # extra nibble
    # The parser will lose the final nibble — but it should not crash.
    # We don't assert equality with _PLAINTEXT because trimming 4 bits
    # mid-ciphertext corrupts the tail; just verify no exception.
    parser = Type1Parser()
    # No exception expected.
    parser.parse(_HEADER, hex_str.encode("ascii"))


# ---------- direct ``parse_binary`` parity path ----------


def test_parse_dispatches_hex_or_binary_same_decrypted_payload() -> None:
    # Same eexec body fed in both forms must produce identical
    # ``decrypted_binary`` payloads — proving the parser dispatches
    # via the same hex_to_binary normalisation in both code paths.
    body = b"dup /Private 3 dict dup begin\n/lenIV 4 def\n/CharStrings 0 dict dup begin end\nend\n"
    cipher_bin = Type1FontUtil.eexec_encrypt(body)
    cipher_hex = Type1FontUtil.hex_encode(cipher_bin).encode("ascii")

    p1 = Type1Parser()
    p1.parse(_HEADER, cipher_bin)
    p2 = Type1Parser()
    p2.parse(_HEADER, cipher_hex)
    assert p1.decrypted_binary == p2.decrypted_binary
    assert b"/Private" in p1.decrypted_binary

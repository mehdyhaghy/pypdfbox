"""Fuzz / edge-case parity tests for the Type 1 PFB + eexec pipeline.

Wave 1567. Hammers the .pfb segment framing (``PfbParser``), the
eexec / charstring stream ciphers (``Type1FontUtil``) and the
lenient ``Type1Parser`` segment-2 entry path with malformed and
boundary inputs, asserting the same lenient-skip-vs-IOException
behaviour that upstream Apache PDFBox 3.0.7 exhibits:

* ``PfbParser`` rejects a missing 0x80 start marker, an unknown record
  type, a negative or oversized declared length, and a payload that
  runs past EOF (the last raising ``EOFException`` upstream → ``EOFError``
  here). It tolerates a PFB with no explicit 0x03 EOF marker.
* ``Type1FontUtil`` eexec/charstring ciphers round-trip, honour
  ``lenIV`` (default 4, also 0), and reject a ciphertext shorter than
  its random prefix.
* ``Type1Parser.parse`` tolerates an empty / sub-4-byte / garbage
  segment 2 (upstream ``createWithPFB`` does not throw on a missing
  Private dict) and never raises out of the binary stage.
"""

from __future__ import annotations

import io
import struct

import pytest

from pypdfbox.fontbox.pfb.pfb_parser import PfbParser
from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import Type1Parser

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_ASCII = 0x01
_BINARY = 0x02
_EOF = 0x03
_START = 0x80


def _rec(record_type: int, payload: bytes) -> bytes:
    """Build one IBM-style PFB record: 0x80, type, le32 size, payload."""
    return bytes((_START, record_type)) + struct.pack("<I", len(payload)) + payload


_SEG1 = b"%!PS-AdobeFont-1.0: Fuzz 001.001\n/FontName /Fuzz def\n"
_SEG2 = bytes(range(64)) * 2  # 128 bytes of "binary" eexec-ish payload


def _valid_pfb(seg1: bytes = _SEG1, seg2: bytes = _SEG2, eof: bool = True) -> bytes:
    data = _rec(_ASCII, seg1) + _rec(_BINARY, seg2)
    if eof:
        data += bytes((_START, _EOF))
    return data


# ---------------------------------------------------------------------------
# PfbParser — happy paths
# ---------------------------------------------------------------------------


def test_valid_pfb_with_eof_marker():
    p = PfbParser(_valid_pfb())
    assert p.get_lengths() == [len(_SEG1), len(_SEG2), 0]
    assert p.get_segment1() == _SEG1
    assert p.get_segment2() == _SEG2
    assert p.size() == len(_SEG1) + len(_SEG2)


def test_valid_pfb_without_eof_marker_is_tolerated():
    # Upstream stops the read loop on EOF once at least one record is read.
    p = PfbParser(_valid_pfb(eof=False))
    assert p.get_segment1() == _SEG1
    assert p.get_segment2() == _SEG2


def test_pfb_from_stream():
    p = PfbParser(io.BytesIO(_valid_pfb()))
    assert p.get_lengths() == [len(_SEG1), len(_SEG2), 0]
    assert isinstance(p.get_input_stream(), io.BytesIO)


def test_pfb_from_bytearray():
    p = PfbParser(bytearray(_valid_pfb()))
    assert p.get_segment2() == _SEG2


def test_trailing_cleartomark_ascii_excluded_from_segment1():
    ctm = b"0" * 512 + b"\ncleartomark\n"
    data = _rec(_ASCII, _SEG1) + _rec(_BINARY, _SEG2) + _rec(_ASCII, ctm)
    data += bytes((_START, _EOF))
    p = PfbParser(data)
    # cleartomark goes to lengths[2], not segment 1.
    assert p.get_segment1() == _SEG1
    assert p.get_lengths()[2] == len(ctm)


def test_class_constants_match_adobe_markers():
    assert PfbParser.START_MARKER == 0x80
    assert PfbParser.ASCII_MARKER == 0x01
    assert PfbParser.BINARY_MARKER == 0x02
    assert PfbParser.EOF_MARKER == 0x03
    assert PfbParser.PFB_HEADER_LENGTH == 18


# ---------------------------------------------------------------------------
# PfbParser — malformed framing
# ---------------------------------------------------------------------------


def test_empty_input_raises():
    with pytest.raises(OSError, match="PFB header missing"):
        PfbParser(b"")


def test_input_shorter_than_header_raises():
    with pytest.raises(OSError, match="PFB header missing"):
        PfbParser(b"\x80\x01\x00\x00")


def test_wrong_start_marker_raises():
    bad = b"\x7f\x01" + struct.pack("<I", 4) + b"abcd" + b"\x00" * 16
    with pytest.raises(OSError, match="Start marker missing"):
        PfbParser(bad)


def test_start_marker_off_by_one_high_raises():
    bad = b"\x81\x01" + struct.pack("<I", 4) + b"abcd" + b"\x00" * 16
    with pytest.raises(OSError, match="Start marker missing"):
        PfbParser(bad)


@pytest.mark.parametrize("record_type", [0x00, 0x04, 0x07, 0x42, 0xFF])
def test_unknown_record_type_raises(record_type):
    bad = bytes((_START, record_type)) + struct.pack("<I", 4) + b"abcd" + b"\x00" * 16
    with pytest.raises(OSError, match="Incorrect record type"):
        PfbParser(bad)


def test_negative_declared_size_raises():
    bad = bytes((_START, _ASCII)) + struct.pack("<i", -1) + b"\x00" * 24
    with pytest.raises(OSError, match="is negative"):
        PfbParser(bad)


def test_high_bit_size_byte_decodes_as_negative():
    # Top size byte >= 0x80 => signed le32 is negative => "is negative" guard,
    # mirroring PDFBox's signed Java-int size composition.
    bad = bytes((_START, _ASCII)) + bytes((0x00, 0x00, 0x00, 0x80)) + b"\x00" * 24
    with pytest.raises(OSError, match="is negative"):
        PfbParser(bad)


def test_oversized_declared_size_raises():
    bad = bytes((_START, _ASCII)) + struct.pack("<I", 0xFFFF) + b"\x00" * 24
    with pytest.raises(OSError, match="larger than the input"):
        PfbParser(bad)


def test_payload_runs_past_eof_raises_eoferror():
    # Second record declares a size that passes the "larger than the input"
    # guard (50 <= total length) but whose payload bytes are not all present,
    # so the actual short read trips PfbParser's EOFException (-> EOFError).
    rec1 = _rec(_ASCII, b"A" * 100)
    rec2 = bytes((_START, _BINARY)) + struct.pack("<I", 50) + b"B" * 5
    bad = rec1 + rec2
    assert len(bad) >= 50  # guarantees we reach the short-read EOF path
    with pytest.raises(EOFError):
        PfbParser(bad)


def test_truncated_payload_definitely_eof():
    # A record declaring a size that fits the input length but whose bytes
    # are cut short by a too-small buffer overall.
    seg1 = _SEG1 * 4  # make input comfortably large
    payload_declared = len(seg1) // 2
    rec1 = _rec(_ASCII, seg1)
    rec2 = bytes((_START, _BINARY)) + struct.pack("<I", payload_declared) + b"\x09" * 3
    bad = rec1 + rec2
    with pytest.raises((EOFError, OSError)):
        PfbParser(bad)


def test_size_field_truncated_at_eof_raises():
    bad = bytes((_START, _ASCII)) + b"\x00\x01" + b"\x00" * 16  # 2 size bytes -> huge
    with pytest.raises(OSError):
        PfbParser(bad)


# ---------------------------------------------------------------------------
# Type1FontUtil — eexec / charstring ciphers
# ---------------------------------------------------------------------------


def test_eexec_roundtrip():
    plain = b"Private dict bytes for round-trip"
    cipher = Type1FontUtil.eexec_encrypt(plain)
    # 4-byte random warm-up prefix added by encrypt.
    assert len(cipher) == len(plain) + 4
    assert Type1FontUtil.eexec_decrypt(cipher) == plain


def test_eexec_decrypt_too_short_for_prefix_raises():
    with pytest.raises(ValueError, match="shorter"):
        Type1FontUtil.eexec_decrypt(b"\x01\x02\x03")


def test_eexec_decrypt_exactly_prefix_length_is_empty():
    cipher = Type1FontUtil.eexec_encrypt(b"")
    assert len(cipher) == 4
    assert Type1FontUtil.eexec_decrypt(cipher) == b""


def test_charstring_roundtrip_default_leniv():
    cs = b"\x8b\x0e\x0d\x09"
    assert Type1FontUtil.charstring_decrypt(Type1FontUtil.charstring_encrypt(cs)) == cs


def test_charstring_roundtrip_leniv_zero():
    cs = b"\xff\x00\x10\x20"
    enc = Type1FontUtil.charstring_encrypt(cs, 0)
    assert len(enc) == len(cs)  # no prefix
    assert Type1FontUtil.charstring_decrypt(enc, 0) == cs


def test_charstring_decrypt_default_leniv_is_four():
    # The default len_iv must be 4 (Adobe spec §6.2 default).
    cs = b"glyph-program-bytes"
    enc = Type1FontUtil.charstring_encrypt(cs)
    assert Type1FontUtil.charstring_decrypt(enc, 4) == cs


def test_generic_encrypt_zero_prefix_is_deterministic():
    a = Type1FontUtil.encrypt(b"deterministic", 55665, 4)
    b = Type1FontUtil.encrypt(b"deterministic", 55665, 4)
    assert a == b  # zero-pad prefix, not random


def test_generic_encrypt_negative_n_raises():
    with pytest.raises(ValueError):
        Type1FontUtil.encrypt(b"x", 55665, -1)


def test_generic_decrypt_shorter_than_prefix_raises():
    with pytest.raises(ValueError):
        Type1FontUtil.decrypt(b"ab", 4330, 4)


def test_eexec_random_prefix_makes_ciphertext_nondeterministic():
    a = Type1FontUtil.eexec_encrypt(b"same plaintext")
    b = Type1FontUtil.eexec_encrypt(b"same plaintext")
    # Different random prefix => different ciphertext, but both decrypt back.
    assert Type1FontUtil.eexec_decrypt(a) == Type1FontUtil.eexec_decrypt(b)


@pytest.mark.parametrize("size", [1, 2, 5, 31, 256])
def test_eexec_roundtrip_varied_lengths(size):
    plain = bytes((i * 7 + 3) & 0xFF for i in range(size))
    assert Type1FontUtil.eexec_decrypt(Type1FontUtil.eexec_encrypt(plain)) == plain


# ---------------------------------------------------------------------------
# Type1FontUtil — hex helpers
# ---------------------------------------------------------------------------


def test_hex_roundtrip():
    data = bytes(range(256))
    assert Type1FontUtil.hex_decode(Type1FontUtil.hex_encode(data)) == data


def test_hex_decode_strips_whitespace():
    assert Type1FontUtil.hex_decode("0a ff\n10\t20") == b"\x0a\xff\x10\x20"


def test_hex_decode_odd_length_raises():
    with pytest.raises(ValueError, match="odd length"):
        Type1FontUtil.hex_decode("abc")


def test_hex_encode_is_uppercase():
    assert Type1FontUtil.hex_encode(b"\xab\xcd") == "ABCD"


# ---------------------------------------------------------------------------
# Type1Parser — lenient segment-2 handling (createWithPFB parity)
# ---------------------------------------------------------------------------


def test_parse_empty_segment2_does_not_throw():
    parser = Type1Parser()
    parser.parse(_SEG1, b"")
    # Missing eexec body => empty decrypted block, no exception.
    assert parser.decrypted_binary == b""


def test_parse_sub_four_byte_segment2_does_not_throw():
    parser = Type1Parser()
    parser.parse(_SEG1, b"\x01\x02")
    assert parser.decrypted_binary == b""


def test_parse_garbage_segment2_does_not_throw():
    parser = Type1Parser()
    # >= 4 bytes of non-hex garbage => treated as binary eexec, decrypted,
    # second-stage parse fails silently (no Private dict) and is swallowed.
    parser.parse(_SEG1, b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22")
    assert isinstance(parser.decrypted_binary, bytes)


def test_parser_decrypt_no_encryption_sentinel():
    # n == -1 is PDFBox's "no encryption" tolerance — returns input verbatim.
    data = b"\x01\x02\x03\x04"
    assert Type1Parser.decrypt(data, Type1Parser.EEXEC_KEY, -1) == data


def test_parser_decrypt_n_exceeds_length_returns_empty():
    assert Type1Parser.decrypt(b"ab", Type1Parser.CHARSTRING_KEY, 4) == b""


def test_parser_decrypt_empty_returns_empty():
    assert Type1Parser.decrypt(b"", Type1Parser.EEXEC_KEY, 4) == b""


def test_parser_is_binary_short_input_is_binary():
    assert Type1Parser.is_binary(b"\x00\x01") is True


def test_parser_is_binary_hex_prefix_is_text():
    assert Type1Parser.is_binary(b"0a1b cdef") is False


def test_parser_is_binary_nonhex_prefix_is_binary():
    assert Type1Parser.is_binary(b"\x80\x01\x02\x03") is True


def test_parser_hex_to_binary_drops_unmatched_nibble():
    # Odd nibble count is truncated, matching upstream new byte[len/2].
    assert Type1Parser.hex_to_binary(b"abcde") == b"\xab\xcd"


def test_parser_hex_to_binary_ignores_separators():
    assert Type1Parser.hex_to_binary(b"ab cd\nef") == b"\xab\xcd\xef"

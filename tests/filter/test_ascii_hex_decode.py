"""Hand-written tests for ``ASCIIHexDecode``."""

from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import ASCIIHexDecode, FilterFactory


def _decode(encoded: bytes, parameters: COSDictionary | None = None) -> bytes:
    out = io.BytesIO()
    ASCIIHexDecode().decode(io.BytesIO(encoded), out, parameters)
    return out.getvalue()


def _encode(raw: bytes) -> bytes:
    out = io.BytesIO()
    ASCIIHexDecode().encode(io.BytesIO(raw), out, None)
    return out.getvalue()


class TestRoundTrip:
    def test_empty_input(self) -> None:
        encoded = _encode(b"")
        assert encoded == b""
        assert _decode(encoded) == b""

    def test_single_byte(self) -> None:
        encoded = _encode(b"\x42")
        assert encoded == b"42"
        assert _decode(encoded) == b"\x42"

    def test_short_text(self) -> None:
        original = "Hi!".encode(encoding="utf-8")
        encoded = _encode(original)
        assert encoded == b"486921"
        assert _decode(encoded) == original

    def test_full_byte_range(self) -> None:
        original = bytes(range(256))
        assert _decode(_encode(original)) == original


class TestEncode:
    def test_encode_uses_pdfbox_uppercase_hex_without_eod(self) -> None:
        assert _encode(b"\xab\xcd\xef") == b"ABCDEF"


class TestDecodeWhitespace:
    def test_decode_skips_whitespace(self) -> None:
        # Whitespace per ISO 32000-1 §7.2.3: NUL TAB LF FF CR SP.
        assert _decode(b"48 65\n6C\t6C\r6F>") == b"Hello"

    def test_decode_with_nul_and_form_feed(self) -> None:
        assert _decode(b"\x00\x0c41\x0042\x0c43>") == b"ABC"

    def test_decode_handles_multi_line_input(self) -> None:
        encoded = b"48656C\r\n6C6F2C20\r\n776F726C\n6421>"
        assert _decode(encoded) == b"Hello, world!"

    def test_decode_uppercase_and_lowercase_digits(self) -> None:
        assert _decode(b"DeAdBeEf>") == b"\xde\xad\xbe\xef"


class TestDecodeEOD:
    def test_decode_stops_at_gt_marker(self) -> None:
        # Bytes after the ``>`` marker must be ignored.
        assert _decode(b"4142>4344") == b"AB"

    def test_decode_without_gt_marker(self) -> None:
        # Spec is permissive — without an EOD marker we still decode
        # whatever hex digits we found.
        assert _decode(b"4142") == b"AB"


class TestDecodeOddDigit:
    def test_odd_trailing_digit_padded_with_zero(self) -> None:
        # "ABC>" → after pad: "ABC0" → bytes 0xAB, 0xC0.
        assert _decode(b"ABC>") == b"\xab\xc0"

    def test_single_digit_padded(self) -> None:
        assert _decode(b"F>") == b"\xf0"


class TestDecodeWhitespaceMidPair:
    # PDFBox's ASCIIHexFilter skips whitespace only before the FIRST nibble
    # of each byte pair — never between the two nibbles. Whitespace that
    # splits a pair is treated as an invalid hex char (REVERSE_HEX = -1).
    # Verified against the live oracle (wave 1412).
    def test_whitespace_between_nibbles_is_not_skipped(self) -> None:
        # "A B C>": A,sp -> 10*16 + (-1) = 159 = 0x9f; B,sp -> 0xaf; C,> -> 0xc0.
        assert _decode(b"A B C>") == b"\x9f\xaf\xc0"


class TestDecodeInvalidChars:
    # PDFBox does NOT raise on a non-hex character: it logs an error and
    # feeds REVERSE_HEX's -1 into the byte arithmetic (low 8 bits kept).
    # Verified against the live oracle (wave 1412).
    def test_non_hex_low_nibble_uses_minus_one(self) -> None:
        # "4Z>": 4*16 + REVERSE_HEX['Z'](-1) = 63 = 0x3f.
        assert _decode(b"4Z>") == b"\x3f"

    def test_non_hex_pair_uses_minus_one_both_nibbles(self) -> None:
        # "GG>": (-1)*16 + (-1) = -17, low 8 bits = 0xef.
        assert _decode(b"GG>") == b"\xef"


class TestDecodeResult:
    def test_bytes_written_and_parameters(self) -> None:
        params = COSDictionary()
        out = io.BytesIO()
        result = ASCIIHexDecode().decode(io.BytesIO(b"4142>"), out, params)
        assert result.bytes_written == 2
        assert out.getvalue() == b"AB"
        assert result.parameters is params


class TestFilterFactoryIntegration:
    def test_long_name_registered(self) -> None:
        assert FilterFactory.is_registered("ASCIIHexDecode")

    def test_short_name_resolves(self) -> None:
        # Short alias ``/AHx`` should resolve to the same instance.
        assert FilterFactory.is_registered("AHx")
        assert FilterFactory.get("AHx") is FilterFactory.get("ASCIIHexDecode")

    def test_factory_returns_ascii_hex_decode_instance(self) -> None:
        assert isinstance(FilterFactory.get("ASCIIHexDecode"), ASCIIHexDecode)

"""Hand-written tests for ``ASCIIHexDecode``."""

from __future__ import annotations

import io

import pytest

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
        # Empty payload still gets the EOD marker.
        assert encoded == b">"
        assert _decode(encoded) == b""

    def test_single_byte(self) -> None:
        encoded = _encode(b"\x42")
        assert encoded == b"42>"
        assert _decode(encoded) == b"\x42"

    def test_short_text(self) -> None:
        original = "Hi!".encode(encoding="utf-8")
        encoded = _encode(original)
        assert encoded == b"486921>"
        assert _decode(encoded) == original

    def test_full_byte_range(self) -> None:
        original = bytes(range(256))
        assert _decode(_encode(original)) == original


class TestEncode:
    def test_encode_uses_lowercase_hex(self) -> None:
        # ``binascii.hexlify`` emits lowercase digits — keep that fact
        # documented so future contributors know the wire format.
        assert _encode(b"\xab\xcd\xef") == b"abcdef>"


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

    def test_odd_trailing_digit_with_whitespace(self) -> None:
        # Whitespace shouldn't change the parity of digit count.
        assert _decode(b"A B C>") == b"\xab\xc0"

    def test_single_digit_padded(self) -> None:
        assert _decode(b"F>") == b"\xf0"


class TestDecodeErrors:
    def test_non_hex_digit_raises_oserror(self) -> None:
        with pytest.raises(OSError):
            _decode(b"4Z>")

    def test_non_hex_pair_raises_oserror(self) -> None:
        with pytest.raises(OSError):
            _decode(b"GG>")


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

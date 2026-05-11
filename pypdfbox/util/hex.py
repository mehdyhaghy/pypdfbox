"""Hex encoding helpers.

Mirrors ``org.apache.pdfbox.util.Hex`` (PDFBox 3.0, ``pdfbox/src/main/java/
org/apache/pdfbox/util/Hex.java``).
"""

from __future__ import annotations

import base64
import logging
import re
from io import BufferedWriter
from typing import BinaryIO

_LOG = logging.getLogger(__name__)

_HEX_CHARS = "0123456789ABCDEF"
_HEX_BYTES = b"0123456789ABCDEF"
_PATTERN_SPACE = re.compile(r"\s")


class Hex:
    """Static-only hex helpers — instances are not supported."""

    def __init__(self) -> None:  # pragma: no cover - mirrors Java private ctor
        raise TypeError("Hex is a utility class")

    @staticmethod
    def get_high_nibble(b: int) -> int:
        """Mirror of ``Hex.getHighNibble`` — upstream private helper."""
        return (b & 0xF0) >> 4

    @staticmethod
    def get_low_nibble(b: int) -> int:
        """Mirror of ``Hex.getLowNibble`` — upstream private helper."""
        return b & 0x0F

    # Backwards-compatible aliases for the previous underscore-prefixed
    # implementation details. Pre-existing callers within pypdfbox.util.hex
    # use these names, so keep them as thin wrappers.
    _high_nibble = get_high_nibble
    _low_nibble = get_low_nibble

    @staticmethod
    def get_string(b: int | bytes | bytearray) -> str:
        """Return uppercase hex for a single byte or a byte sequence."""
        if isinstance(b, (bytes, bytearray)):
            return "".join(
                _HEX_CHARS[Hex._high_nibble(x)] + _HEX_CHARS[Hex._low_nibble(x)]
                for x in b
            )
        x = b & 0xFF
        return _HEX_CHARS[Hex._high_nibble(x)] + _HEX_CHARS[Hex._low_nibble(x)]

    @staticmethod
    def get_bytes(b: int | bytes | bytearray) -> bytes:
        """Return the ASCII hex encoding of the given byte(s) as bytes."""
        if isinstance(b, (bytes, bytearray)):
            out = bytearray(len(b) * 2)
            for i, x in enumerate(b):
                out[i * 2] = _HEX_BYTES[Hex._high_nibble(x)]
                out[i * 2 + 1] = _HEX_BYTES[Hex._low_nibble(x)]
            return bytes(out)
        x = b & 0xFF
        return bytes([_HEX_BYTES[Hex._high_nibble(x)], _HEX_BYTES[Hex._low_nibble(x)]])

    @staticmethod
    def get_chars(num: int) -> str:
        """Return four hex chars for a 16-bit short (big-endian nibbles)."""
        num &= 0xFFFF
        return (
            _HEX_CHARS[(num >> 12) & 0x0F]
            + _HEX_CHARS[(num >> 8) & 0x0F]
            + _HEX_CHARS[(num >> 4) & 0x0F]
            + _HEX_CHARS[num & 0x0F]
        )

    @staticmethod
    def get_chars_utf16_be(text: str) -> str:
        """Return UTF-16BE hex of a string — one 4-char run per code unit."""
        # Java strings are UTF-16; emulate by encoding to UTF-16BE.
        data = text.encode("utf-16-be")
        out = []
        for i in range(0, len(data), 2):
            high = data[i]
            low = data[i + 1]
            out.append(_HEX_CHARS[(high >> 4) & 0x0F])
            out.append(_HEX_CHARS[high & 0x0F])
            out.append(_HEX_CHARS[(low >> 4) & 0x0F])
            out.append(_HEX_CHARS[low & 0x0F])
        return "".join(out)

    @staticmethod
    def write_hex_byte(b: int, output: BinaryIO | BufferedWriter) -> None:
        """Write the ASCII hex bytes of a single byte to ``output``."""
        x = b & 0xFF
        output.write(bytes([_HEX_BYTES[Hex._high_nibble(x)]]))
        output.write(bytes([_HEX_BYTES[Hex._low_nibble(x)]]))

    @staticmethod
    def write_hex_bytes(data: bytes | bytearray, output: BinaryIO | BufferedWriter) -> None:
        """Write the ASCII hex encoding of ``data`` to ``output``."""
        for b in data:
            Hex.write_hex_byte(b, output)

    @staticmethod
    def decode_base64(base64_value: str) -> bytes:
        """Decode a base64 string after stripping all whitespace."""
        stripped = _PATTERN_SPACE.sub("", base64_value)
        return base64.b64decode(stripped)

    @staticmethod
    def decode_hex(s: str) -> bytes:
        """Decode an ASCII-hex string. Aborts at first non-hex pair."""
        out = bytearray()
        i = 0
        while i < len(s) - 1:
            c = s[i]
            if c == "\n" or c == "\r":
                i += 1
                continue
            value = 16 * Hex.get_hex_value(s[i]) + Hex.get_hex_value(s[i + 1])
            if value >= 0:
                out.append(value)
            else:
                hex_byte = s[i : i + 2]
                _LOG.error("Can't parse %s, aborting decode", hex_byte)
                break
            i += 2
        return bytes(out)

    @staticmethod
    def get_hex_value(c: str) -> int:
        """Return the nibble value of ``c`` or -256 if invalid."""
        if "0" <= c <= "9":
            return ord(c) - ord("0")
        if "A" <= c <= "F":
            return ord(c) - ord("A") + 10
        if "a" <= c <= "f":
            return ord(c) - ord("a") + 10
        return -256


__all__ = ["Hex"]

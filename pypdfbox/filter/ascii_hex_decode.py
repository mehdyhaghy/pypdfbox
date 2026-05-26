from __future__ import annotations

import binascii
from typing import BinaryIO, Final

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# Whitespace bytes per ISO 32000-1 §7.2.3 — the exact set
# ``ASCIIHexFilter.isWhitespace`` skips upstream: NUL TAB LF FF CR SP.
_WHITESPACE: frozenset[int] = frozenset(b"\x00\t\n\x0c\r ")
_EOD: int = ord(">")

# REVERSE_HEX lookup matching upstream's ``ASCIIHexFilter`` table: a hex
# digit byte maps to its 0..15 nibble value; everything else (including
# whitespace bytes — which the per-nibble path does NOT pre-skip) maps to
# -1 exactly as PDFBox does, so the same byte arithmetic and overflow wrap
# reproduce on malformed input.
_REVERSE_HEX: Final[list[int]] = [-1] * 256
for _c in range(ord("0"), ord("9") + 1):
    _REVERSE_HEX[_c] = _c - ord("0")
for _c in range(ord("A"), ord("F") + 1):
    _REVERSE_HEX[_c] = _c - ord("A") + 10
for _c in range(ord("a"), ord("f") + 1):
    _REVERSE_HEX[_c] = _c - ord("a") + 10


class ASCIIHexDecode(Filter):
    """
    ``/ASCIIHexDecode`` filter (ISO 32000-1 §7.4.2).

    Encode is a thin adapter over :func:`binascii.hexlify`. Decode mirrors
    upstream ``org.apache.pdfbox.filter.ASCIIHexFilter.decode`` byte-for-byte
    (verified against the live PDFBox 3.0.7 oracle, wave 1412), including its
    quirks on malformed input:

    * Whitespace (NUL TAB LF FF CR SP) is skipped ONLY before the *first*
      nibble of each byte pair — never between the two nibbles. Whitespace
      that splits a pair is therefore treated as an invalid hex character.
    * An invalid (non-hex) character does NOT raise; PDFBox logs an error and
      feeds the lookup's ``-1`` into ``value = REVERSE_HEX[hi]*16 +
      REVERSE_HEX[lo]``, writing the low 8 bits. We mirror that (logging is a
      Java-plumbing detail we skip per the porting conventions).
    * The ``>`` end-of-data marker stops decoding; an odd trailing nibble
      before EOD/EOF is written with a low nibble of 0.

    Mirrors `org.apache.pdfbox.filter.ASCIIHexFilter`.
    """

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        raw = encoded.read()
        n = len(raw)
        out = bytearray()
        i = 0
        while i < n:
            # Skip whitespace before the first nibble of the next pair.
            first = raw[i]
            i += 1
            while first in _WHITESPACE:
                if i >= n:
                    first = -1
                    break
                first = raw[i]
                i += 1
            if first == -1 or first == _EOD:
                break
            value = _REVERSE_HEX[first] * 16
            # The low nibble is read WITHOUT a whitespace skip — upstream
            # parity. EOF/EOD here writes the high nibble with a 0 low.
            if i >= n:
                out.append(value & 0xFF)
                break
            second = raw[i]
            i += 1
            if second == _EOD:
                out.append(value & 0xFF)
                break
            value += _REVERSE_HEX[second]
            out.append(value & 0xFF)

        bytes_written = decoded.write(bytes(out))
        flush = getattr(decoded, "flush", None)
        if callable(flush):
            flush()
        out_params = parameters if parameters is not None else COSDictionary()
        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        encoded.write(binascii.hexlify(raw.read()).upper())
        flush = getattr(encoded, "flush", None)
        if callable(flush):
            flush()

    def is_decompression_input_size_known(self) -> bool:
        return False


FilterFactory.register("ASCIIHexDecode", ASCIIHexDecode())

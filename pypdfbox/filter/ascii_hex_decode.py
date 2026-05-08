from __future__ import annotations

import binascii
from typing import BinaryIO

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# Whitespace bytes per ISO 32000-1 §7.2.3 — same set used by ``BaseParser``.
_WHITESPACE: frozenset[int] = frozenset(b"\x00\t\n\x0c\r ")
_EOD: int = ord(">")


class ASCIIHexDecode(Filter):
    """
    ``/ASCIIHexDecode`` filter (ISO 32000-1 §7.4.2).

    Thin adapter over :func:`binascii.unhexlify` / :func:`binascii.hexlify`.
    The PDF-specific behaviours — whitespace tolerance, ``>`` end-of-data
    marker, and odd-trailing-digit zero-pad — are original.

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

        # Strip whitespace and stop at the EOD marker.
        cleaned = bytearray()
        for b in raw:
            if b == _EOD:
                break
            if b in _WHITESPACE:
                continue
            cleaned.append(b)

        # Pad odd-length sequences with a trailing '0' per spec
        # ("If the filter encounters the EOD marker after reading an odd
        # number of hexadecimal digits, it shall behave as if a 0
        # followed the last digit").
        if len(cleaned) % 2 == 1:
            cleaned.append(ord("0"))

        try:
            data = binascii.unhexlify(bytes(cleaned))
        except binascii.Error as exc:
            raise OSError(f"ASCIIHexDecode: {exc}") from exc

        bytes_written = decoded.write(data)
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
        encoded.write(binascii.hexlify(raw.read()))
        encoded.write(b">")
        flush = getattr(encoded, "flush", None)
        if callable(flush):
            flush()

    def is_decompression_input_size_known(self) -> bool:
        return False


FilterFactory.register("ASCIIHexDecode", ASCIIHexDecode())

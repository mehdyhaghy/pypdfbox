from __future__ import annotations

import base64
import binascii
from typing import BinaryIO, Final

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# ISO 32000-1 §7.4.3 ASCII85Decode.
#
# Encoding maps groups of 4 binary bytes onto 5 ASCII characters in base 85,
# offset by 33 (so the digits run from b'!' (33) to b'u' (33 + 84 = 117)).
# A 4-zero group has the special abbreviation b'z' (a single byte). A trailing
# group of 1, 2, or 3 bytes is encoded as 2, 3, or 4 base-85 digits with the
# missing low bytes padded as zeros and the corresponding low digits trimmed.
# The encoded stream is terminated by b'~>'. Whitespace inside the stream is
# ignored on decode.
#
# The Python stdlib (``base64.a85encode`` / ``base64.a85decode``) implements
# this exact base-85 numerical scheme — including the b'z' shortcut on encode
# and whitespace skipping plus b'<~' / b'~>' framing on decode — so this
# filter is a thin adapter per PRD §3.7. The PDF-specific bits we own are:
#   * no leading b'<~' on encode (PDFBox / PDF spec uses only the b'~>' tail);
#   * trim trailing newline that ``a85encode`` does not append (it doesn't);
#   * surface invalid input as ``OSError`` for parser-friendly handling;
#   * reject a b'z' that appears mid-group (stdlib already enforces this in
#     strict mode but we double-check for a clearer error message).

_EOD: Final[bytes] = b"~>"
_WHITESPACE: Final[frozenset[int]] = frozenset(b" \t\n\r\f\v\x00")


class ASCII85Decode(Filter):
    """ASCII85Decode filter (ISO 32000-1 §7.4.3).

    Mirrors `org.apache.pdfbox.filter.ASCII85Filter`.
    """

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        # Pull the whole encoded stream up-front. PDF ASCII85 segments are
        # small in practice (text/inline images), and the stdlib decoder is
        # not incremental.
        data = encoded.read()
        decoded_bytes = self._decode_bytes(data)
        decoded.write(decoded_bytes)
        return DecodeResult(parameters if parameters is not None else COSDictionary())

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        data = raw.read()
        # Adobe-mode a85encode wraps with b'<~' ... b'~>'; the PDF variant
        # has no leading marker, so strip the prefix the stdlib added.
        framed = base64.a85encode(data, adobe=True)
        # framed always starts with b'<~' and ends with b'~>'.
        encoded.write(framed[2:])

    @staticmethod
    def _decode_bytes(data: bytes) -> bytes:
        # Strip everything after (and including) the EOD marker, if present.
        eod = data.find(_EOD)
        if eod >= 0:
            data = data[:eod]
        # Drop whitespace; we need to validate range and detect a misplaced
        # b'z' ourselves before handing what's left to the stdlib decoder.
        cleaned = bytearray()
        col = 0  # position within the current 5-char group
        for byte in data:
            if byte in _WHITESPACE:
                continue
            if byte == 0x7A:  # b'z'
                if col != 0:
                    raise OSError("ASCII85: 'z' shortcut found mid-group")
                cleaned.append(byte)
                # b'z' is a complete 4-byte group on its own; col stays 0.
                continue
            if byte < 0x21 or byte > 0x75:  # outside b'!'..b'u'
                raise OSError(f"ASCII85: byte {byte!r} out of range '!'..'u'")
            cleaned.append(byte)
            col = (col + 1) % 5
        if not cleaned:
            return b""
        try:
            return base64.a85decode(bytes(cleaned), adobe=False)
        except (ValueError, binascii.Error) as exc:
            raise OSError(f"ASCII85: decode failed: {exc}") from exc


FilterFactory.register("ASCII85Decode", ASCII85Decode())

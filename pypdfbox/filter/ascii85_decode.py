from __future__ import annotations

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
# The encoder frames the stream with a trailing b'~>'. On DECODE upstream's
# ASCII85InputStream actually ends the stream at the FIRST b'~' byte alone (the
# b'>' is incidental); whatever follows that b'~' is never read. The Adobe b'<~'
# intro is NOT special-cased — b'<' is an ordinary base-85 digit. Whitespace
# inside the stream is ignored on decode.
#
# ENCODE delegates to ``ASCII85OutputStream`` (mirroring upstream
# ``ASCII85Filter.encode``, which wraps its destination in that stream). The
# wrapper owns the exact base-85 numerical scheme — including the b'z'
# shortcut — plus the PDF framing PDFBox emits byte-for-byte: hard line breaks
# every 72 chars and the b'~>' EOD marker followed by a trailing LF.
#
# Decode reproduces the accumulator of upstream's
# ``org.apache.pdfbox.filter.ASCII85InputStream`` exactly, verified
# byte-for-byte against the live PDFBox oracle (wave 1412). The relevant
# upstream rules (PDFBox 3.0.7) that the stdlib strict decoder could NOT
# match — and that an earlier value-based port got wrong — are:
#
#   * Whitespace ignored on decode is ONLY LF (0x0a), CR (0x0d) and SPACE
#     (0x20). PDFBox does NOT skip NUL / TAB / FF / VT; those bytes are
#     digits and fall under the range check below.
#   * A digit byte ``c`` contributes ``c - '!'`` to the base-85 accumulator.
#     PDFBox raises ("Invalid data in Ascii85 stream") iff ``c - '!'`` is
#     ``< 0 or > 93`` — i.e. it accepts the whole range b'!'(0x21)..b'}'
#     (0x7d) as a digit (b'~' (0x7e) being the EOD byte stripped above),
#     wider than the b'!'..b'u' the encoder ever emits, and lets the 32-bit
#     wrap mask any per-group overflow.
#   * The b'z' 4-zero shortcut fires ONLY at a group boundary. Mid-group a
#     b'z' is an ordinary digit (0x7a - 0x21 = 89).
#   * A trailing partial group of ``n`` digits is padded with b'u' and yields
#     ``n - 1`` bytes; a lone single digit (n == 1) yields nothing and is
#     dropped silently.
#
# (PDFBox decoding a stream that lacks the b'~>' marker can read past EOF and
# duplicate output — a harness artifact, not a real-PDF case; real PDF
# ASCII85 streams always carry the b'~>' terminator, so we honour it strictly.)

# Upstream ASCII85InputStream treats the single byte b'~' (0x7e) as end-of-data
# on its own: its read loop returns EOF the moment it sees b'~', without
# requiring the b'>' that the encoder pairs with it. A stream therefore ends at
# the FIRST b'~', whatever (if anything) follows it. Two consequences this
# byte-for-byte parity (verified against the live PDFBox 3.0.7 oracle, wave
# 1523) depends on:
#   * b'87cURD~X' decodes the b'87cURD' body and stops at b'~' (the trailing
#     b'X' is never seen), NOT only at the literal pair b'~>'.
#   * The Adobe b'<~' intro marker is NOT special-cased by the filter. b'<' is
#     an ordinary base-85 digit (0x3c - '!' = 27) and the b'~' immediately
#     after it terminates the stream — so b'<~...~>' yields a lone leading
#     digit that is dropped (a partial group of 1), i.e. zero bytes, exactly as
#     upstream produces. (Real PDF ASCII85 streams omit the b'<~' intro.)
_EOD: Final[int] = 0x7E  # b'~' — end-of-data byte (the b'>' that follows is incidental)
# Upstream ASCII85InputStream skips only LF, CR and SPACE — NOT NUL/TAB/FF/VT.
_WHITESPACE: Final[frozenset[int]] = frozenset(b"\n\r ")
_Z: Final[int] = 0x7A  # b'z' — 4-zero-byte shortcut at a group boundary
_DIGIT_OFFSET: Final[int] = 0x21  # b'!' — base-85 digit zero
_DIGIT_MAX: Final[int] = 93  # c - '!' must be in 0..93 (b'!'..b'~'); else invalid
_U32_MASK: Final[int] = 0xFFFFFFFF


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
        bytes_written = decoded.write(decoded_bytes)
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
        # Mirror upstream ``ASCII85Filter.encode``: wrap the destination in
        # an ``ASCII85OutputStream`` and copy the raw bytes through it. The
        # output stream owns the PDF-specific framing pypdfbox must emit
        # byte-for-byte: base-85 body, hard line breaks every 72 chars, and
        # the ``~>`` EOD marker followed by a trailing newline. (Encoding the
        # body via ``base64.a85encode`` directly is NOT byte-equal to upstream
        # — it skips the line-folding and the terminating LF.)
        #
        # Local import keeps the codec module free of a load-time dependency
        # on the output-stream wrapper (which itself imports base64 / io).
        from .ascii85_output_stream import ASCII85OutputStream  # noqa: PLC0415

        data = raw.read()
        sink = ASCII85OutputStream(encoded)
        sink.write(data)
        # ``flush()`` emits the full encoded body + ``~>\n`` to ``encoded``.
        # The surrounding encode chain reads ``encoded.getvalue()`` after we
        # return, so the destination must stay open: upstream closes its
        # wrapper but its destination is a ``ByteArrayOutputStream`` whose
        # contents survive close, whereas pypdfbox's destination is a live
        # ``BytesIO``. Flush, then detach the destination so the wrapper's
        # finaliser (``RawIOBase.__del__`` → ``close()``) cannot close it.
        sink.flush()
        sink.detach()

    def is_decompression_input_size_known(self) -> bool:
        return False

    @staticmethod
    def _decode_bytes(data: bytes) -> bytes:
        # Strip everything from the first EOD byte (b'~') onward, if present.
        # Upstream's ASCII85InputStream ends the stream at the first b'~', not
        # only at the literal b'~>' pair (the b'>' is incidental framing).
        eod = data.find(_EOD)
        if eod >= 0:
            data = data[:eod]

        out = bytearray()
        group: list[int] = []  # base-85 digits buffered for the current group

        def flush_full() -> None:
            value = 0
            for digit in group:
                value = value * 85 + (digit - _DIGIT_OFFSET)
            value &= _U32_MASK
            out.extend(
                ((value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
            )
            group.clear()

        for byte in data:
            if byte in _WHITESPACE:
                continue
            if byte == _Z and not group:
                # b'z' shortcut: four zero bytes — but only at a group
                # boundary. Mid-group it is an ordinary digit (see below).
                out.extend(b"\x00\x00\x00\x00")
                continue
            # Upstream's range check: (byte - '!') must be in 0..93. Bytes
            # below b'!' (and not whitespace) or above b'~' are rejected.
            if byte - _DIGIT_OFFSET < 0 or byte - _DIGIT_OFFSET > _DIGIT_MAX:
                raise OSError("Invalid data in Ascii85 stream")
            group.append(byte)
            if len(group) == 5:
                flush_full()

        # Trailing partial group of n digits yields n-1 output bytes. A lone
        # single digit (n == 1) yields nothing and is silently dropped.
        n = len(group)
        if n >= 2:
            padded = group + [ord("u")] * (5 - n)
            value = 0
            for digit in padded:
                value = value * 85 + (digit - _DIGIT_OFFSET)
            value &= _U32_MASK
            for shift in (24, 16, 8, 0)[: n - 1]:
                out.append((value >> shift) & 0xFF)

        return bytes(out)


FilterFactory.register("ASCII85Decode", ASCII85Decode())

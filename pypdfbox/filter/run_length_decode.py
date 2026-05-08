from __future__ import annotations

from typing import BinaryIO, Final

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# ISO 32000-1 §7.4.5 RunLengthDecode.
#
# The encoded byte stream is a sequence of (length, payload) packets:
#
#   length in 0..127  -> next ``length + 1`` bytes are copied verbatim
#   length == 128     -> end-of-data marker (no further bytes consumed)
#   length in 129..255-> next single byte is repeated ``257 - length`` times
#
# This filter is original PDF-specific code (no stdlib equivalent). The
# encoder mirrors the greedy state machine in
# ``org.apache.pdfbox.filter.RunLengthDecodeFilter`` (PDFBox 3.0.x) so that
# round-trips against PDFBox-encoded streams remain bit-identical.

_EOD: Final[int] = 128
_MAX_RUN: Final[int] = 128  # max literal-or-repeat run length per packet

# Upstream-named alias for the ``128`` end-of-data marker. Java has it
# as ``private static final int RUN_LENGTH_EOD = 128`` on the filter
# class; porters who translate that constant verbatim land here.
RUN_LENGTH_EOD: Final[int] = _EOD


def _read_exact(encoded: BinaryIO, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = encoded.read(size - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


class RunLengthDecode(Filter):
    """RunLengthDecode filter (ISO 32000-1 §7.4.5).

    Mirrors `org.apache.pdfbox.filter.RunLengthDecodeFilter`.
    """

    # Mirror of upstream's ``RUN_LENGTH_EOD`` constant. Exposed as a
    # class attribute so callers can write ``RunLengthDecode.RUN_LENGTH_EOD``
    # the way upstream tests reference it via ``RunLengthDecodeFilter``.
    RUN_LENGTH_EOD: Final[int] = _EOD

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        bytes_written = 0
        while True:
            length_byte = encoded.read(1)
            if not length_byte:
                # PDFBox treats EOF without an EOD marker as a clean stop,
                # but for our parser we want to flag truncation explicitly:
                # any preceding length byte that promised more data should
                # have been consumed below. Reaching EOF here means the
                # stream simply lacked the b'\x80' EOD; that's lenient and
                # matches PDFBox behavior, so just stop.
                break
            length = length_byte[0]
            if length == _EOD:
                break
            if length < _EOD:
                want = length + 1
                chunk = _read_exact(encoded, want)
                if len(chunk) != want:
                    raise OSError(
                        f"RunLengthDecode: truncated literal run "
                        f"(wanted {want} bytes, got {len(chunk)})"
                    )
                decoded.write(chunk)
                bytes_written += len(chunk)
            else:
                repeat_byte = encoded.read(1)
                if not repeat_byte:
                    raise OSError("RunLengthDecode: truncated repeat run (missing payload byte)")
                repeat_count = 257 - length
                decoded.write(repeat_byte * repeat_count)
                bytes_written += repeat_count
        out_params = parameters if parameters is not None else COSDictionary()
        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        # Greedy state machine ported from PDFBox 3.0.x RunLengthDecodeFilter.
        # ``equality`` is True when ``buf`` (or rather, the trailing run) is
        # currently a string of identical bytes; False when it's a literal
        # mixed run staged in ``buf``.
        data = raw.read()
        out = bytearray()
        buf = bytearray(_MAX_RUN)
        last_val = -1
        count = 0
        equality = False

        for byt in data:
            if last_val == -1:
                last_val = byt
                count = 1
                continue
            if count == _MAX_RUN:
                if equality:
                    # max-length repeat run: 129 means "repeat next byte twice"
                    # ... wait: 257 - 129 = 128, so this flushes 128 copies.
                    out.append(_EOD + 1)  # 129
                    out.append(last_val)
                else:
                    # max-length literal run: 127 means "next 128 bytes literal"
                    out.append(_MAX_RUN - 1)  # 127
                    out.extend(buf[:_MAX_RUN])
                equality = False
                last_val = byt
                count = 1
            elif count == 1:
                if byt == last_val:
                    equality = True
                else:
                    buf[0] = last_val
                    buf[1] = byt
                    last_val = byt
                count = 2
            else:
                # 1 < count < 128
                if byt == last_val:
                    if equality:
                        count += 1
                    else:
                        # We were building a literal run but just hit a repeat.
                        # Flush all but the last byte as a literal, then start
                        # a 2-byte equality run from the duplicated byte.
                        out.append(count - 2)
                        out.extend(buf[: count - 1])
                        count = 2
                        equality = True
                else:
                    if equality:
                        # equality ends here; flush the repeat run.
                        out.append(257 - count)
                        out.append(last_val)
                        equality = False
                        count = 1
                    else:
                        buf[count] = byt
                        count += 1
                    last_val = byt

        if count > 0:
            if count == 1:
                out.append(0)
                out.append(last_val)
            elif equality:
                out.append(257 - count)
                out.append(last_val)
            else:
                out.append(count - 1)
                out.extend(buf[:count])
        out.append(_EOD)
        encoded.write(bytes(out))


FilterFactory.register("RunLengthDecode", RunLengthDecode())

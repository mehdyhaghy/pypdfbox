"""Parser for Adobe Printer Font Binary (``.pfb``) files.

Mirrors ``org.apache.fontbox.pfb.PfbParser`` (PDFBox 3.0,
``fontbox/src/main/java/org/apache/fontbox/pfb/PfbParser.java``).

The output mirrors upstream: the three segment lengths (ASCII, binary,
trailing ASCII) and the concatenated bytes minus the IBM-style record
headers. A Type 1 font can then be reconstructed by reading
``[0:lengths[0]]`` as ASCII, ``[lengths[0]:lengths[0]+lengths[1]]`` as
the encrypted binary, and the remainder as the final ``cleartomark``
segment.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO

_LOG = logging.getLogger(__name__)

_PFB_HEADER_LENGTH = 18
_START_MARKER = 0x80
_ASCII_MARKER = 0x01
_BINARY_MARKER = 0x02
_EOF_MARKER = 0x03
_BUFFER_SIZE = 0xFFFF


class PfbParser:
    """Splits a ``.pfb`` payload into its three logical segments."""

    PFB_HEADER_LENGTH = _PFB_HEADER_LENGTH
    START_MARKER = _START_MARKER
    ASCII_MARKER = _ASCII_MARKER
    BINARY_MARKER = _BINARY_MARKER
    EOF_MARKER = _EOF_MARKER
    BUFFER_SIZE = _BUFFER_SIZE

    def __init__(self, source: str | Path | BinaryIO | bytes | bytearray) -> None:
        if isinstance(source, (str, Path)):
            data = Path(source).read_bytes()
        elif isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        else:
            data = self._read_fully(source)
        self._lengths: list[int] = [0, 0, 0]
        self._pfbdata: bytes = b""
        self._parse_pfb(data)

    # ------------------------------------------------------------------
    def read_fully(self, stream: BinaryIO) -> bytes:
        """Mirror of upstream's ``readFully`` — drain ``stream``."""
        out = bytearray()
        while True:
            chunk = stream.read(_BUFFER_SIZE)
            if not chunk:
                break
            out.extend(chunk)
        return bytes(out)

    _read_fully = read_fully

    def parse_pfb(self, pfb: bytes) -> None:
        if len(pfb) < _PFB_HEADER_LENGTH:
            raise OSError("PFB header missing")

        type_list: list[int] = []
        seg_list: list[bytes] = []
        stream = io.BytesIO(pfb)
        total = 0
        while True:
            r = stream.read(1)
            if not r:
                if total > 0:
                    break
                raise OSError("PFB header missing")
            if r[0] != _START_MARKER:
                raise OSError("Start marker missing")
            rec_byte = stream.read(1)
            if not rec_byte:
                raise OSError("EOF while reading PFB header")
            record_type = rec_byte[0]
            if record_type == _EOF_MARKER:
                break
            if record_type not in (_ASCII_MARKER, _BINARY_MARKER):
                raise OSError(f"Incorrect record type: {record_type}")
            size_bytes = stream.read(4)
            if len(size_bytes) != 4:
                raise OSError("EOF while reading PFB size")
            size = (
                size_bytes[0]
                | (size_bytes[1] << 8)
                | (size_bytes[2] << 16)
                | (size_bytes[3] << 24)
            )
            _LOG.debug("record type: %d, segment size: %d", record_type, size)
            if size < 0:
                raise OSError(f"record size {size} is negative")
            if size > len(pfb):
                raise OSError(
                    f"record size {size} would be larger than the input"
                )
            ar = stream.read(size)
            if len(ar) != size:
                raise EOFError("EOF while reading PFB font")
            total += size
            type_list.append(record_type)
            seg_list.append(ar)

        if total > len(pfb):
            raise OSError(f"total record size {total} would be larger than the input")

        out = bytearray(total)
        cleartomark_segment: bytes | None = None
        dst_pos = 0

        # copy ASCII segments first (skip trailing cleartomark — placed at end).
        for i, kind in enumerate(type_list):
            if kind != _ASCII_MARKER:
                continue
            ar = seg_list[i]
            if (
                i == len(type_list) - 1
                and len(ar) < 600
                and b"cleartomark" in ar
            ):
                cleartomark_segment = ar
                continue
            out[dst_pos : dst_pos + len(ar)] = ar
            dst_pos += len(ar)
        self._lengths[0] = dst_pos

        for i, kind in enumerate(type_list):
            if kind != _BINARY_MARKER:
                continue
            ar = seg_list[i]
            out[dst_pos : dst_pos + len(ar)] = ar
            dst_pos += len(ar)
        self._lengths[1] = dst_pos - self._lengths[0]

        if cleartomark_segment is not None:
            out[dst_pos : dst_pos + len(cleartomark_segment)] = cleartomark_segment
            self._lengths[2] = len(cleartomark_segment)
            dst_pos += len(cleartomark_segment)

        self._pfbdata = bytes(out[:dst_pos])

    _parse_pfb = parse_pfb

    # ------------------------------------------------------------------
    def get_lengths(self) -> list[int]:
        return self._lengths

    def get_pfbdata(self) -> bytes:
        return self._pfbdata

    def get_input_stream(self) -> BinaryIO:
        return io.BytesIO(self._pfbdata)

    def size(self) -> int:
        return len(self._pfbdata)

    def get_segment1(self) -> bytes:
        return self._pfbdata[: self._lengths[0]]

    def get_segment2(self) -> bytes:
        return self._pfbdata[self._lengths[0] : self._lengths[0] + self._lengths[1]]


__all__ = ["PfbParser"]

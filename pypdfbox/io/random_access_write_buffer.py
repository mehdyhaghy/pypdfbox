from __future__ import annotations

import io

from .random_access_write import RandomAccessWrite


class RandomAccessWriteBuffer(RandomAccessWrite):
    """
    In-memory random-access write sink. Thin adapter over ``io.BytesIO``.
    Per PRD §3.7, generic byte buffering delegates to stdlib.
    """

    def __init__(self) -> None:
        self._buf = io.BytesIO()
        self._closed = False

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed RandomAccessWriteBuffer")

    def write(self, b: int) -> None:
        self._check_open()
        if not 0 <= b <= 0xFF:
            raise ValueError("byte value must be in 0..255")
        self._buf.write(bytes((b,)))

    def write_bytes(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        self._check_open()
        if length is None:
            length = len(data) - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > len(data):
            raise ValueError("offset/length out of range for data")
        self._buf.write(memoryview(data)[offset : offset + length])

    def clear(self) -> None:
        self._check_open()
        self._buf = io.BytesIO()

    def close(self) -> None:
        if not self._closed:
            self._buf.close()
            self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    # Python convenience — extract the written bytes. Not part of the PDFBox API.
    def to_bytes(self) -> bytes:
        self._check_open()
        return self._buf.getvalue()

    def length(self) -> int:
        self._check_open()
        return self._buf.getbuffer().nbytes

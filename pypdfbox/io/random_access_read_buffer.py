from __future__ import annotations

import io
from typing import BinaryIO

from .random_access_read import RandomAccessRead


class RandomAccessReadBuffer(RandomAccessRead):
    """
    In-memory random-access reader. Thin adapter over ``io.BytesIO``.

    PDFBox's upstream implementation uses a list of fixed-size byte chunks
    to avoid one-shot allocation of huge arrays under Java's signed-int
    array length limit. CPython's ``BytesIO`` has no such constraint and is
    implemented in C, so we delegate. Observable behavior (reads, seeks,
    EOF, length) is identical.
    """

    def __init__(self, source: bytes | bytearray | memoryview | BinaryIO) -> None:
        if isinstance(source, (bytes, bytearray, memoryview)):
            self._buf = io.BytesIO(bytes(source))
        elif hasattr(source, "read"):
            data = source.read()
            if not isinstance(data, (bytes, bytearray)):
                raise TypeError("source stream must yield bytes")
            self._buf = io.BytesIO(bytes(data))
        else:
            raise TypeError(f"unsupported source type: {type(source).__name__}")
        self._length = self._buf.getbuffer().nbytes
        self._closed = False

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> RandomAccessReadBuffer:
        return cls(data)

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> RandomAccessReadBuffer:
        return cls(stream)

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed RandomAccessReadBuffer")

    def read(self) -> int:
        self._check_open()
        b = self._buf.read(1)
        return b[0] if b else self.EOF

    def read_into(
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        self._check_open()
        if length is None:
            length = len(buf) - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > len(buf):
            raise ValueError("offset/length out of range for buf")
        if self._buf.tell() >= self._length:
            return self.EOF if length > 0 else 0
        view = memoryview(buf)[offset : offset + length]
        return self._buf.readinto(view)

    def get_position(self) -> int:
        self._check_open()
        return self._buf.tell()

    def seek(self, position: int) -> None:
        self._check_open()
        if position < 0 or position > self._length:
            raise ValueError(f"seek position {position} out of range [0, {self._length}]")
        self._buf.seek(position)

    def length(self) -> int:
        self._check_open()
        return self._length

    def close(self) -> None:
        if not self._closed:
            self._buf.close()
            self._closed = True

    def is_closed(self) -> bool:
        return self._closed

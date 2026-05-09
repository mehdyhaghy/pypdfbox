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

    # Mirrors upstream RandomAccessReadBuffer.DEFAULT_CHUNK_SIZE_4KB.
    # Our BytesIO-backed implementation does not actually chunk, but the
    # public constant is part of the upstream API surface.
    DEFAULT_CHUNK_SIZE_4KB: int = 1 << 12

    def __init__(self, source: bytes | bytearray | memoryview | BinaryIO) -> None:
        if isinstance(source, (bytes, bytearray, memoryview)):
            self._buf = io.BytesIO(bytes(source))
        else:
            read = getattr(source, "read", None)
            if read is None:
                raise TypeError(f"unsupported source type: {type(source).__name__}")
            if not callable(read):
                raise TypeError("source read attribute must be callable")
            chunks: list[bytes] = []
            try:
                data = read(self.DEFAULT_CHUNK_SIZE_4KB)
            except TypeError:
                data = read()
                if not isinstance(data, (bytes, bytearray, memoryview)):
                    raise TypeError("source stream must yield bytes") from None
                if not data:
                    data = b""
                else:
                    chunks.append(bytes(data))
            else:
                while True:
                    if not isinstance(data, (bytes, bytearray, memoryview)):
                        raise TypeError("source stream must yield bytes")
                    if not data:
                        break
                    chunks.append(bytes(data))
                    data = read(self.DEFAULT_CHUNK_SIZE_4KB)
            self._buf = io.BytesIO(b"".join(chunks))
        self._length = self._buf.getbuffer().nbytes
        self._closed = False

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> RandomAccessReadBuffer:
        return cls(data)

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> RandomAccessReadBuffer:
        return cls(stream)

    @classmethod
    def create_buffer_from_stream(cls, stream: BinaryIO) -> RandomAccessReadBuffer:
        """
        Create a buffer from ``stream`` and close ``stream`` afterwards.

        Mirrors upstream
        ``RandomAccessReadBuffer.createBufferFromStream(InputStream)``,
        which copies the stream into memory and then calls
        ``inputStream.close()`` on the source. Whether copying succeeds or
        raises, the source is closed.
        """
        try:
            buf = cls(stream)
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        return buf

    # Upstream Java alias (camelCase mirror).
    createBufferFromStream = create_buffer_from_stream  # noqa: N815

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
        if position < 0:
            raise OSError(f"invalid seek position {position}")
        # PDFBox semantics: seeking past end clamps to end, leaving stream at EOF.
        target = min(position, self._length)
        self._buf.seek(target)

    def length(self) -> int:
        self._check_open()
        return self._length

    def close(self) -> None:
        if not self._closed:
            self._buf.close()
            self._closed = True

    def is_closed(self) -> bool:
        return self._closed

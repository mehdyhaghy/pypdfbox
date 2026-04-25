from __future__ import annotations

import contextlib
from typing import BinaryIO, Protocol

DEFAULT_COPY_BUFFER: int = 8192


class _Closeable(Protocol):
    def close(self) -> None: ...


def copy(in_stream: BinaryIO, out_stream: BinaryIO, buffer_size: int = DEFAULT_COPY_BUFFER) -> int:
    """
    Copy all bytes from ``in_stream`` to ``out_stream``. Returns the total
    number of bytes copied.
    """
    if buffer_size <= 0:
        raise ValueError("buffer_size must be > 0")
    total = 0
    while True:
        chunk = in_stream.read(buffer_size)
        if not chunk:
            break
        out_stream.write(chunk)
        total += len(chunk)
    return total


def to_byte_array(in_stream: BinaryIO, buffer_size: int = DEFAULT_COPY_BUFFER) -> bytes:
    """Read ``in_stream`` to EOF and return its contents as bytes."""
    chunks: list[bytes] = []
    while True:
        chunk = in_stream.read(buffer_size)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def close_quietly(closeable: _Closeable | None) -> None:
    """Close ``closeable`` if non-None; suppress any exception."""
    if closeable is None:
        return
    with contextlib.suppress(Exception):
        closeable.close()


def populate_buffer(in_stream: BinaryIO, buffer: bytearray) -> int:
    """
    Fill ``buffer`` from ``in_stream``. Returns the number of bytes actually
    read; less than ``len(buffer)`` indicates EOF was reached.
    """
    total = 0
    target = len(buffer)
    mv = memoryview(buffer)
    while total < target:
        chunk = in_stream.read(target - total)
        if not chunk:
            break
        n = len(chunk)
        mv[total : total + n] = chunk
        total += n
    return total

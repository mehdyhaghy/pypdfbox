from __future__ import annotations

import contextlib
import logging
from typing import BinaryIO, Protocol

DEFAULT_COPY_BUFFER: int = 8192

_log = logging.getLogger(__name__)


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


def close_and_log_exception(
    closeable: _Closeable,
    logger: logging.Logger,
    resource_name: str,
    initial_exception: BaseException | None = None,
) -> BaseException | None:
    """Close an I/O resource, logging (but not raising) any failure.

    Mirrors upstream ``IOUtils.closeAndLogException`` in semantics:

    * Always attempts ``closeable.close()``.
    * On failure, logs a warning with ``resource_name``.
    * Returns the new exception only when ``initial_exception`` is ``None``
      — so callers can carry forward an in-flight error without losing it.
    * Returns ``initial_exception`` unchanged when it was supplied (whether
      or not close succeeded).
    """
    try:
        closeable.close()
    except Exception as exc:
        logger.warning("Error closing %s: %s", resource_name, exc)
        if initial_exception is None:
            return exc
    return initial_exception


def unmap(buf: object) -> None:
    """No-op stub for parity with upstream ``IOUtils.unmap``.

    Upstream releases JVM memory-mapped ``ByteBuffer`` instances eagerly
    via ``sun.misc.Unsafe`` because the JVM otherwise pins the underlying
    file. CPython's ``mmap`` releases its file lock when the object is
    garbage-collected (or its ``close()`` is called), so the explicit
    unmap step is unnecessary here. We accept any object so call sites
    can be ported mechanically; if the object exposes ``close()`` we call
    it as a best-effort hook (matches the pragmatic intent of the
    upstream method).
    """
    if buf is None:
        return
    close = getattr(buf, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()

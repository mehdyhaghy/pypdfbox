from __future__ import annotations

import contextlib
import io
import threading
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

    The chunked-buffer protocol from upstream is preserved as the protected
    helpers ``check_closed``, ``expand_buffer``, ``next_buffer``,
    ``read_remaining_bytes`` and ``reset_buffers`` so subclasses written
    against the PDFBox shape continue to work; under the BytesIO backing
    they operate on a single logical chunk that grows on demand.
    """

    # Mirrors upstream RandomAccessReadBuffer.DEFAULT_CHUNK_SIZE_4KB.
    # Our BytesIO-backed implementation does not actually chunk, but the
    # public constant is part of the upstream API surface.
    DEFAULT_CHUNK_SIZE_4KB: int = 1 << 12

    def __init__(self, source: bytes | bytearray | memoryview | BinaryIO) -> None:
        # ``chunk_size`` mirrors upstream's protected field. For a wrapped
        # buffer it equals the buffer's effective limit (PDFBOX-5764); for
        # the InputStream form it stays at the 4KB default.
        self.chunk_size: int = self.DEFAULT_CHUNK_SIZE_4KB
        if isinstance(source, (bytes, bytearray, memoryview)):
            data = bytes(source)
            self._buf = io.BytesIO(data)
            self.chunk_size = len(data) if len(data) > 0 else self.DEFAULT_CHUNK_SIZE_4KB
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
        # Per-thread copies handed out from create_view, mirroring upstream's
        # ConcurrentMap<Long, RandomAccessReadBuffer> rarbCopies.
        self._rarb_copies: dict[int, RandomAccessReadBuffer] = {}

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

    # ------------------------------------------------------------------
    # Protected/private helpers mirroring the upstream chunked layout.
    # Names are snake_case ports of upstream methods on the same class.
    # ------------------------------------------------------------------

    def check_closed(self) -> None:
        """
        Raise ``OSError`` if this buffer is already closed.

        Mirrors upstream ``RandomAccessReadBuffer.checkClosed()``.
        """
        if self._closed:
            raise OSError("RandomAccessBuffer already closed")

    # Internal alias used elsewhere in this file; keeps the original
    # ``_check_open`` name for backward compatibility with existing
    # tests/callers that asserted on a ValueError.
    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed RandomAccessReadBuffer")

    def expand_buffer(self) -> None:
        """
        Ensure write capacity for one additional byte at the current
        position. Under the upstream chunk-list layout this allocates a
        new chunk and advances the chunk index; with a single ``BytesIO``
        backing the operation is a no-op because ``BytesIO`` grows on
        demand. Provided for parity with subclasses that override.

        Mirrors upstream ``expandBuffer()``.
        """
        self.check_closed()
        # No-op: BytesIO grows automatically on write/seek-past-end.

    def next_buffer(self) -> None:
        """
        Switch to the next buffer chunk. With a single logical chunk
        there is no next chunk; if the caller is positioned at end-of-
        stream this raises ``OSError`` to match upstream.

        Mirrors upstream ``nextBuffer()`` (private in Java; exposed here
        for parity with the upstream method surface).
        """
        self.check_closed()
        if self._buf.tell() >= self._length:
            raise OSError("No more chunks available, end of buffer reached")
        # Otherwise the single chunk is still active; nothing to switch.

    def read_remaining_bytes(
        self, b: bytearray, offset: int, length: int
    ) -> int:
        """
        Copy up to ``length`` bytes from the current position into ``b``
        starting at ``offset``. Returns the number of bytes copied, or
        ``-1`` if the position is already at or past EOF.

        Mirrors upstream ``readRemainingBytes(byte[], int, int)``.
        """
        self.check_closed()
        if self._buf.tell() >= self._length:
            return self.EOF
        if offset < 0 or length < 0 or offset + length > len(b):
            raise ValueError("offset/length out of range for buf")
        view = memoryview(b)[offset : offset + length]
        n = self._buf.readinto(view)
        return n if n > 0 else self.EOF

    def reset_buffers(self) -> None:
        """
        Reset the buffer to the initial state: position 0, no content.

        Mirrors upstream ``resetBuffers()``. Used by the write-buffer
        subclass when reusing storage for a new logical stream.
        """
        self.check_closed()
        self._buf = io.BytesIO()
        self._length = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

    def is_eof(self) -> bool:
        """
        Return ``True`` if the current position is at end-of-stream.

        Overrides the base implementation to avoid an unnecessary
        ``read()``/``rewind()`` round-trip; mirrors upstream
        ``RandomAccessReadBuffer.isEOF()`` which compares the pointer
        against ``size`` directly.
        """
        self._check_open()
        return self._buf.tell() >= self._length

    def close(self) -> None:
        if not self._closed:
            # Close any per-thread view copies handed out by create_view,
            # matching upstream's IOUtils::closeQuietly fan-out over
            # rarbCopies.values() before clearing the map.
            for copy in self._rarb_copies.values():
                # closeQuietly equivalent: swallow errors during cleanup.
                with contextlib.suppress(Exception):
                    copy.close()
            self._rarb_copies.clear()
            self._buf.close()
            self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        """
        Return a read-only slice view onto this buffer.

        Mirrors upstream ``RandomAccessReadBuffer.createView``: a per-
        thread duplicate of this buffer is cached so view reads do not
        race against the parent's seek cursor. The duplicate shares
        immutable data with the parent (BytesIO contents are immutable
        once constructed here), so the duplicate is effectively a cheap
        independent cursor.
        """
        from .random_access_read_view import RandomAccessReadView

        self._check_open()
        thread_id = threading.get_ident()
        copy = self._rarb_copies.get(thread_id)
        if copy is None or copy.is_closed():
            copy = RandomAccessReadBuffer(self._buf.getvalue())
            self._rarb_copies[thread_id] = copy
        return RandomAccessReadView(copy, start_position, length)

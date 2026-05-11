from __future__ import annotations

import io

from .random_access import RandomAccess
from .random_access_read_buffer import RandomAccessReadBuffer


class RandomAccessReadWriteBuffer(RandomAccessReadBuffer, RandomAccess):
    """In-memory random-access reader+writer backed by ``io.BytesIO``.

    Mirrors upstream
    ``org.apache.pdfbox.io.RandomAccessReadWriteBuffer`` (a subclass of
    ``RandomAccessReadBuffer`` that also implements ``RandomAccess``).
    Upstream uses a fixed-chunk byte-buffer list to dodge Java's signed
    array length limit; CPython's ``BytesIO`` has no such constraint so
    we delegate writes directly to it.
    """

    DEFAULT_CHUNK_SIZE_4KB: int = 1 << 12

    def __init__(self, defined_chunk_size: int | None = None) -> None:
        # Start empty; upstream's no-arg + chunkSize ctors both produce
        # a buffer ready for first write.
        super().__init__(b"")
        if defined_chunk_size is not None and defined_chunk_size > 0:
            self.chunk_size = defined_chunk_size

    # ------------------------------------------------------------------
    # RandomAccessWrite contract
    # ------------------------------------------------------------------

    def write(self, b: int | bytes | bytearray | memoryview) -> None:  # type: ignore[override]
        """Write a single byte (``int``) or a bytes-like object.

        Mirrors upstream ``write(int)`` / ``write(byte[], int, int)`` /
        ``write(byte[])`` overloads.
        """
        self._check_open()
        data: bytes
        if isinstance(b, int):
            if not 0 <= b <= 0xFF:
                raise ValueError("byte value must be in 0..255")
            data = bytes((b,))
        else:
            data = bytes(b)
        self._buf.write(data)
        self._length = max(self._length, self._buf.tell())

    def write_bytes(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        """Write ``length`` bytes from ``data`` starting at ``offset``.

        Mirrors upstream ``RandomAccessWrite.writeBytes`` semantics
        (3-arg ``write(byte[], int, int)``).
        """
        self._check_open()
        view = memoryview(data)
        if length is None:
            length = view.nbytes - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > view.nbytes:
            raise ValueError("offset/length out of range for data")
        self._buf.write(view[offset : offset + length])
        self._length = max(self._length, self._buf.tell())

    def clear(self) -> None:
        """Discard all stored bytes and reset the position to zero.

        Mirrors upstream ``RandomAccessReadWriteBuffer.clear`` (Java
        line 47).
        """
        self._check_open()
        self._buf = io.BytesIO()
        self._length = 0

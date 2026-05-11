from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .random_access_write import RandomAccessWrite


class RandomAccessOutputStream(io.RawIOBase):
    """An ``OutputStream``-style adapter over a ``RandomAccessWrite``.

    Mirrors upstream
    ``org.apache.pdfbox.io.RandomAccessOutputStream`` (Java class). The
    adapter does not maintain its own position — each ``COSStream`` only
    has one writer, so the underlying ``RandomAccessWrite`` cursor is
    authoritative.
    """

    def __init__(self, writer: RandomAccessWrite) -> None:
        super().__init__()
        self._writer: RandomAccessWrite = writer

    def writable(self) -> bool:
        return True

    def write(self, b: bytes | bytearray | memoryview | int) -> int:  # type: ignore[override]
        """Write a single byte (``int``) or a bytes-like object.

        Mirrors upstream ``write(int)`` / ``write(byte[], int, int)`` /
        ``write(byte[])`` overloads.
        """
        if isinstance(b, int):
            self._writer.write(b & 0xFF)
            return 1
        view = memoryview(b)
        self._writer.write_bytes(view, 0, view.nbytes)
        return view.nbytes

    def write_with_offset(
        self,
        b: bytes | bytearray | memoryview,
        offset: int,
        length: int,
    ) -> None:
        """3-arg ``write(byte[], int, int)`` parity helper.

        Mirrors upstream ``RandomAccessOutputStream.write(byte[], int,
        int)`` (Java line 44). Python's ``write(b)`` already handles the
        2-arg form via slicing; this helper preserves the upstream
        signature for ports that translate the call site literally.
        """
        self._writer.write_bytes(b, offset, length)

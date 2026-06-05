from __future__ import annotations

import io

from .random_access_write import RandomAccessWrite


def _as_byte_view(data: bytes | bytearray | memoryview) -> memoryview:
    view = memoryview(data)
    try:
        return view.cast("B")
    except TypeError:
        return memoryview(bytes(view))


class RandomAccessWriteBuffer(RandomAccessWrite):
    """
    In-memory write sink. Thin adapter over ``io.BytesIO``.
    """

    def __init__(self) -> None:
        self._buf = io.BytesIO()
        self._closed = False

    def _check_open(self) -> None:
        # Upstream parity: the write-capable in-memory buffer
        # (RandomAccessReadWriteBuffer) inherits checkClosed() from
        # RandomAccessReadBuffer, which throws
        # ``IOException("RandomAccessBuffer already closed")``. We map
        # IOException → OSError with the exact upstream message.
        if self._closed:
            raise OSError("RandomAccessBuffer already closed")

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
        view = _as_byte_view(data)
        if length is None:
            length = view.nbytes - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > view.nbytes:
            raise ValueError("offset/length out of range for data")
        self._buf.write(view[offset : offset + length])

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

    def is_empty(self) -> bool:
        """True when no bytes have been written (or after :meth:`clear`)."""
        self._check_open()
        return self._buf.getbuffer().nbytes == 0

    def tell(self) -> int:
        """
        Current write position, in bytes. Python file-like idiom; equivalent
        to the underlying ``BytesIO.tell()``.
        """
        self._check_open()
        return self._buf.tell()

    def __len__(self) -> int:
        return self.length()

    def __bytes__(self) -> bytes:
        return self.to_bytes()

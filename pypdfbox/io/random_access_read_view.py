from __future__ import annotations

from .random_access_read import RandomAccessRead


class RandomAccessReadView(RandomAccessRead):
    """
    A read-only slice view onto another ``RandomAccessRead``.

    The view exposes positions ``[0, length)`` that map to the parent's
    ``[start_position, start_position + length)``. The parent's seek/read
    cursor is moved on every operation; do not assume parent position is
    preserved across view operations.
    """

    def __init__(
        self,
        parent: RandomAccessRead,
        start_position: int,
        length: int,
        close_parent: bool = False,
    ) -> None:
        if start_position < 0:
            raise ValueError("start_position must be non-negative")
        if length < 0:
            raise ValueError("length must be non-negative")
        # PDFBox upstream does not validate that start_position + length fits
        # within the parent: the view is a logical window; reads stop at
        # parent EOF or view EOF, whichever comes first.
        self._parent = parent
        self._start = start_position
        self._length = length
        self._position = 0
        self._close_parent = close_parent
        self._closed = False

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed RandomAccessReadView")

    def read(self) -> int:
        self._check_open()
        if self._position >= self._length:
            return self.EOF
        self._parent.seek(self._start + self._position)
        b = self._parent.read()
        if b != self.EOF:
            self._position += 1
        return b

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
        if length == 0:
            return 0
        if self._position >= self._length:
            return self.EOF
        remaining = min(length, self._length - self._position)
        self._parent.seek(self._start + self._position)
        n = self._parent.read_into(buf, offset, remaining)
        if n > 0:
            self._position += n
        return n

    def get_position(self) -> int:
        self._check_open()
        return self._position

    def seek(self, position: int) -> None:
        self._check_open()
        if position < 0:
            raise OSError(f"invalid seek position {position}")
        # PDFBox semantics: seeking past end clamps to end, leaving stream at EOF.
        self._position = min(position, self._length)

    def length(self) -> int:
        self._check_open()
        return self._length

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._close_parent:
                self._parent.close()

    def is_closed(self) -> bool:
        return self._closed

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        # PDFBox upstream forbids nested views on a RandomAccessReadView.
        raise OSError("createView() not supported on a RandomAccessReadView")

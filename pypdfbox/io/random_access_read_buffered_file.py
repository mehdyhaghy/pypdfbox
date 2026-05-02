from __future__ import annotations

import io
import os
from pathlib import Path

from .random_access_read import RandomAccessRead


class RandomAccessReadBufferedFile(RandomAccessRead):
    """
    File-backed random-access reader. Thin adapter over ``io.BufferedReader``
    (which provides stdlib-managed read-ahead buffering on top of a raw file
    descriptor). Lazy: only the bytes you read are pulled from disk.
    """

    def __init__(
        self,
        path: str | os.PathLike[str],
        buffer_size: int = io.DEFAULT_BUFFER_SIZE,
    ) -> None:
        self._path = Path(path)
        self._length = self._path.stat().st_size
        raw = io.FileIO(os.fspath(self._path), "rb")
        self._buf = io.BufferedReader(raw, buffer_size=buffer_size)
        self._closed = False

    @property
    def path(self) -> Path:
        return self._path

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed RandomAccessReadBufferedFile")

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
        n = self._buf.readinto(view)
        return n if n is not None else 0

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

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        """
        Return a read-only slice view onto this file.

        Mirrors upstream ``RandomAccessReadBufferedFile.createView``: a fresh
        underlying file handle is opened so the view can be read without
        contending with the parent's seek cursor (thread-safety guarantee
        from upstream). The view owns its underlying handle and closes it
        when the view is closed.
        """
        from .random_access_read_view import RandomAccessReadView

        self._check_open()
        sibling = RandomAccessReadBufferedFile(self._path)
        return RandomAccessReadView(
            sibling, start_position, length, close_parent=True
        )

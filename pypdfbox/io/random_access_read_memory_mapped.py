from __future__ import annotations

import mmap
import os
from pathlib import Path

from .random_access_read import RandomAccessRead


class RandomAccessReadMemoryMapped(RandomAccessRead):
    """
    Random-access reader backed by ``mmap.mmap``. Best for very large files
    where kernel-managed page caching outperforms userspace buffering.
    Read-only; write support would require COW semantics that vary by OS.

    Opt-in: not the default for file inputs (mmap has caveats around NFS,
    Windows file locks, and 32-bit address space). Callers should use
    ``RandomAccessReadBufferedFile`` unless they have a measured reason
    to mmap.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._length = self._path.stat().st_size
        self._fd = os.open(os.fspath(self._path), os.O_RDONLY)
        try:
            if self._length == 0:
                # mmap rejects zero-length files; behave as an empty source.
                self._mm: mmap.mmap | None = None
            else:
                # POSIX takes ``prot=PROT_READ``; Windows takes ``access=ACCESS_READ``
                # (the Windows ``mmap`` module exposes no PROT_* constants).
                if hasattr(mmap, "PROT_READ"):
                    self._mm = mmap.mmap(self._fd, 0, prot=mmap.PROT_READ)
                else:
                    self._mm = mmap.mmap(self._fd, 0, access=mmap.ACCESS_READ)
        except Exception:
            os.close(self._fd)
            raise
        self._position = 0
        self._closed = False

    @property
    def path(self) -> Path:
        return self._path

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed RandomAccessReadMemoryMapped")

    def read(self) -> int:
        self._check_open()
        if self._position >= self._length or self._mm is None:
            return self.EOF
        b = self._mm[self._position]
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
        if self._position >= self._length or self._mm is None:
            return self.EOF if length > 0 else 0
        n = min(length, self._length - self._position)
        buf[offset : offset + n] = self._mm[self._position : self._position + n]
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
        if self._closed:
            return
        self._closed = True
        if self._mm is not None:
            self._mm.close()
            self._mm = None
        os.close(self._fd)

    def is_closed(self) -> bool:
        return self._closed

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        """
        Return a read-only slice view onto this memory-mapped file.

        Mirrors upstream ``RandomAccessReadMemoryMappedFile.createView``: a
        fresh underlying mapping is created so the view can be read without
        contending with the parent's position cursor. The view owns the
        sibling and closes it on view close.
        """
        from .random_access_read_view import RandomAccessReadView

        self._check_open()
        sibling = RandomAccessReadMemoryMapped(self._path)
        return RandomAccessReadView(
            sibling, start_position, length, close_parent=True
        )

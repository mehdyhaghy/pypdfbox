from __future__ import annotations

import io
import os
import tempfile
from typing import BinaryIO

from .memory_usage_setting import UNLIMITED, MemoryUsageSetting, StorageMode
from .random_access_read import RandomAccessRead
from .random_access_write import RandomAccessWrite

_BytesIO = io.BytesIO


class ScratchFileBuffer(RandomAccessRead, RandomAccessWrite):
    """
    Read+write buffer backed by either ``io.BytesIO`` (memory-only mode)
    or ``tempfile.SpooledTemporaryFile`` (mixed mode — spills to disk
    after the memory threshold) or an unspooled temp file (disk-only).

    Created exclusively by ``ScratchFile.create_buffer()``. Closing the
    parent ``ScratchFile`` closes all buffers it created.
    """

    def __init__(self, backing: BinaryIO, owner: ScratchFile) -> None:
        self._backing = backing
        self._owner = owner
        self._closed = False

    # Both base ABCs define context-manager helpers; resolve the diamond explicitly.
    def __enter__(self) -> ScratchFileBuffer:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed ScratchFileBuffer")

    # ----- RandomAccessRead -----

    def read(self) -> int:
        self._check_open()
        b = self._backing.read(1)
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
        if self.get_position() >= self.length():
            return self.EOF if length > 0 else 0
        view = memoryview(buf)[offset : offset + length]
        n = self._backing.readinto(view)  # type: ignore[attr-defined]
        return n if n is not None else 0

    def get_position(self) -> int:
        self._check_open()
        return self._backing.tell()

    def seek(self, position: int) -> None:
        self._check_open()
        if position < 0:
            raise ValueError("position must be non-negative")
        self._backing.seek(position)

    def length(self) -> int:
        self._check_open()
        cur = self._backing.tell()
        self._backing.seek(0, os.SEEK_END)
        end = self._backing.tell()
        self._backing.seek(cur)
        return end

    def is_closed(self) -> bool:
        return self._closed

    # ----- RandomAccessWrite -----

    def write(self, b: int) -> None:
        self._check_open()
        if not 0 <= b <= 0xFF:
            raise ValueError("byte value must be in 0..255")
        self._backing.write(bytes((b,)))

    def write_bytes(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        self._check_open()
        if length is None:
            length = len(data) - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > len(data):
            raise ValueError("offset/length out of range for data")
        self._backing.write(memoryview(data)[offset : offset + length])

    def clear(self) -> None:
        self._check_open()
        self._backing.seek(0)
        self._backing.truncate(0)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._backing.close()
        self._owner._buffer_closed(self)


class ScratchFile:
    """
    Factory for read+write buffers used to hold parsed/decoded PDF object
    streams without unbounded memory pressure.

    Backed by ``tempfile.SpooledTemporaryFile`` in MIXED mode, plain
    ``BytesIO`` in MAIN_MEMORY_ONLY, and an unspooled ``TemporaryFile``
    in TEMP_FILE_ONLY. Per PRD §3.7, page-based scratch storage is
    delegated to stdlib's spooled temp file.
    """

    def __init__(self, setting: MemoryUsageSetting | None = None) -> None:
        self._setting = setting or MemoryUsageSetting.setup_main_memory_only()
        self._open_buffers: set[ScratchFileBuffer] = set()
        self._closed = False

    @property
    def setting(self) -> MemoryUsageSetting:
        return self._setting

    def create_buffer(self) -> ScratchFileBuffer:
        if self._closed:
            raise ValueError("ScratchFile is closed")
        mode = self._setting.mode
        backing: BinaryIO
        if mode is StorageMode.MAIN_MEMORY_ONLY:
            backing = _BytesIO()
        elif mode is StorageMode.TEMP_FILE_ONLY:
            backing = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115 — closed by buffer
        else:  # MIXED
            spool_max = (
                self._setting.max_main_memory_bytes
                if self._setting.max_main_memory_bytes != UNLIMITED
                else 16 * 1024 * 1024  # 16 MiB default spill threshold
            )
            # SpooledTemporaryFile is BinaryIO-compatible at runtime but its stub
            # types it as IO[bytes]; cast for mypy.
            backing = tempfile.SpooledTemporaryFile(  # noqa: SIM115 — closed by buffer
                max_size=spool_max, mode="w+b"
            )  # type: ignore[assignment]
        buf = ScratchFileBuffer(backing, self)
        self._open_buffers.add(buf)
        return buf

    def create_buffer_from_input(self, source: RandomAccessRead) -> ScratchFileBuffer:
        """Convenience: copy ``source`` (from current position to end) into a new buffer."""
        buf = self.create_buffer()
        chunk = bytearray(8192)
        while True:
            n = source.read_into(chunk)
            if n <= 0:
                break
            buf.write_bytes(chunk, 0, n)
        buf.seek(0)
        return buf

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for buf in list(self._open_buffers):
            buf.close()
        self._open_buffers.clear()

    def _buffer_closed(self, buf: ScratchFileBuffer) -> None:
        self._open_buffers.discard(buf)

    def __enter__(self) -> ScratchFile:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


__all__ = ["ScratchFile", "ScratchFileBuffer"]

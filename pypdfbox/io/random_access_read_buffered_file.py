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
        self.check_closed()

    # Upstream parity: Java RandomAccessReadBufferedFile#checkClosed (line 265)
    # is package-private and raises ``IOException(getClass().getName() +
    # " already closed")`` → ``OSError`` per the project's IOException
    # mapping. The message reproduces the fully-qualified upstream class
    # name so a caller inspecting the message sees the same string.
    def check_closed(self) -> None:
        if self._closed:
            raise OSError(
                "org.apache.pdfbox.io.RandomAccessReadBufferedFile already closed"
            )

    # NOTE on the repeated inline ``if self._closed: raise OSError(...)``
    # guards below: ``read`` / ``peek`` / ``seek`` / ``get_position`` /
    # ``rewind`` are the tokenizer's per-byte hot path (millions of calls
    # per parse). Inlining the guard avoids two extra Python frames
    # (``_check_open`` -> ``check_closed``) per call. The exception type and
    # message are identical to ``check_closed``, which is kept for external
    # callers.

    def read(self) -> int:
        if self._closed:
            raise OSError(
                "org.apache.pdfbox.io.RandomAccessReadBufferedFile already closed"
            )
        b = self._buf.read(1)
        return b[0] if b else self.EOF

    def peek(self) -> int:
        """Read one byte without advancing position. Returns 0..255 or -1.

        Overrides the base ``read()``+``rewind(1)`` round-trip with a
        direct buffered read and an in-buffer relative seek back;
        observable behavior (closed-check error, EOF result, unchanged
        position) is identical.
        """
        if self._closed:
            raise OSError(
                "org.apache.pdfbox.io.RandomAccessReadBufferedFile already closed"
            )
        buf = self._buf
        b = buf.read(1)
        if b:
            buf.seek(-1, io.SEEK_CUR)
            return b[0]
        return self.EOF

    def rewind(self, n: int) -> None:
        """Move position back by ``n`` bytes (negative ``n`` seeks forward).

        Overrides the base ``seek(get_position() - n)`` chain with a
        direct buffered seek; validation and clamping match ``seek``
        exactly.
        """
        if self._closed:
            raise OSError(
                "org.apache.pdfbox.io.RandomAccessReadBufferedFile already closed"
            )
        buf = self._buf
        position = buf.tell() - n
        if position < 0:
            raise OSError(f"Invalid position {position}")
        buf.seek(min(position, self._length))

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
        if self._closed:
            raise OSError(
                "org.apache.pdfbox.io.RandomAccessReadBufferedFile already closed"
            )
        return self._buf.tell()

    def seek(self, position: int) -> None:
        if self._closed:
            raise OSError(
                "org.apache.pdfbox.io.RandomAccessReadBufferedFile already closed"
            )
        if position < 0:
            raise OSError(f"Invalid position {position}")
        # PDFBox semantics: seeking past end clamps to end, leaving stream at EOF.
        target = min(position, self._length)
        self._buf.seek(target)

    def length(self) -> int:
        # Upstream RandomAccessReadBufferedFile.length() (Java line 237) does
        # NOT call checkClosed() — it returns the cached file length even
        # after close(). Mirror that: no close guard here.
        return self._length

    def close(self) -> None:
        if not self._closed:
            self._buf.close()
            self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    # Upstream parity: Java RandomAccessReadBufferedFile#isEOF (line 274)
    # explicitly overrides RandomAccessRead.isEOF; mirror that here so the
    # method shows up on this class, not just on the base. Semantics match
    # the base via peek().
    def is_eof(self) -> bool:
        return self.peek() == self.EOF

    # Upstream parity: Java RandomAccessReadBufferedFile uses a LinkedHashMap
    # LRU page cache (PAGE_SIZE = 4096, MAX_CACHED_PAGES = 1000). The Python
    # port relies on stdlib ``io.BufferedReader`` for lazy/buffered reads, so
    # we don't need an explicit page cache. The two helpers below mirror the
    # upstream method names so callers / parity scripts that look for them
    # find a stable surface.

    # Mirrors upstream private ``RandomAccessReadBufferedFile.readPage`` (line 160).
    # Allocates a fresh ``PAGE_SIZE`` (4096) byte page from the current file
    # position. Used only as a parity-named helper — pypdfbox's normal read
    # path goes through ``io.BufferedReader``.
    PAGE_SIZE: int = 1 << 12  # 4096
    MAX_CACHED_PAGES: int = 1000

    def read_page(self) -> bytes:
        """Read up to ``PAGE_SIZE`` bytes from the current position.

        Mirrors upstream private ``RandomAccessReadBufferedFile.readPage``
        which fills a 4 KiB ``ByteBuffer`` from the file channel. Returns
        the bytes actually read (may be shorter than ``PAGE_SIZE`` near
        EOF). The Python port reuses ``io.BufferedReader`` for buffering
        in normal operation; this helper is exposed for parity.
        """
        self._check_open()
        return self._buf.read(self.PAGE_SIZE)

    def remove_eldest_entry(self, eldest: object | None = None) -> bool:
        """LRU page-cache eviction predicate.

        Mirrors upstream ``LinkedHashMap.removeEldestEntry`` override at
        line 57: returns ``True`` once the cache has more than
        ``MAX_CACHED_PAGES`` (1000) entries. The Python port doesn't keep
        an explicit page cache (``io.BufferedReader`` handles buffering)
        so this always returns ``False`` — the predicate is provided for
        parity-named call sites.
        """
        return False

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

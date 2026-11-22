import io
import os
from pathlib import Path

from .random_access_read import RandomAccessRead

# Window cache used by the parser's chunk-scanning fast paths (see
# ``RandomAccessReadBufferedFile._read_window``). 64 pages of 64 KiB keep the
# same 4 MiB budget as upstream's page cache (1000 pages of 4 KiB).
_WINDOW_PAGE_SHIFT = 16
_WINDOW_PAGE_SIZE = 1 << _WINDOW_PAGE_SHIFT
_WINDOW_MAX_PAGES = 64
# ``os.pread`` reads at an offset without moving the shared cursor; Windows
# has no ``pread``, so a second read-only handle serves the windows there.
_HAS_PREAD = hasattr(os, "pread")


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
        self._fd = raw.fileno()
        # Window cache state, see ``_read_window``: page number -> page
        # bytes (oldest first), and the size / mtime the pages are valid for.
        # A file that fits the ``BufferedReader`` buffer never uses it.
        self._pages: dict[int, bytes] = {}
        self._window_fh: io.FileIO | None = None
        self._window_cache = self._length > buffer_size
        self._mtime_ns = os.fstat(self._fd).st_mtime_ns
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
            self._pages.clear()
            window_fh = self._window_fh
            if window_fh is not None:
                self._window_fh = None
                window_fh.close()
            self._buf.close()
            self._closed = True

    # ---------- window reads for the parser's fast paths ----------

    def _pread(self, size: int, offset: int) -> bytes:
        """Up to ``size`` bytes at ``offset``, leaving the cursor and the
        ``BufferedReader`` state untouched."""
        if _HAS_PREAD:
            return os.pread(self._fd, size, offset)
        fh = self._window_fh
        if fh is None:
            fh = self._window_fh = io.FileIO(os.fspath(self._path), "rb")
        fh.seek(offset)
        return fh.read(size)

    def _read_window(self, start: int, size: int) -> bytes | None:
        """Exactly ``size`` bytes of the file from offset ``start``, or
        ``None`` when the file no longer holds them (it shrank underneath).

        Private helper of the parser's chunk-scanning fast paths. Their
        reference reads a window through the cursor (seek, read, seek back).
        Indirect objects are visited in object-number order, not file order,
        so in a file larger than the ``BufferedReader`` buffer that costs a
        seek plus a read system call per object. Such a file serves the
        window from a small FIFO cache of 64 KiB pages read at an offset
        instead, leaving the cursor and the buffer alone. Before reading a
        page the file is checked for the size and modification time it had
        when it was opened; once it has changed (for example a document saved
        over its own source) the cache is dropped for good. Like upstream's
        page cache, a page already read keeps the bytes it was read with. A
        file that fits the buffer (read once, then served from memory), or
        one that has changed, takes the reference read.
        """
        if self._closed:
            raise OSError(
                "org.apache.pdfbox.io.RandomAccessReadBufferedFile already closed"
            )
        if self._window_cache:
            data = self._cached_window(start, size)
            if data is not False:
                return data  # type: ignore[return-value]
        buf = self._buf
        buf.seek(start)
        data = buf.read(size)
        buf.seek(start)
        return data if len(data) == size else None

    def _cached_window(self, start: int, size: int) -> bytes | bool | None:
        """``_read_window`` from the page cache; ``False`` when the file has
        changed and the reference read must run instead."""
        if size > _WINDOW_PAGE_SIZE:
            if not self._unchanged():
                return False
            data = self._pread(size, start)
            return data if len(data) == size else None
        pages = self._pages
        index = start >> _WINDOW_PAGE_SHIFT
        offset = start & (_WINDOW_PAGE_SIZE - 1)
        end = offset + size
        page = pages.get(index)
        if page is None:
            page = self._load_page(index)
            if page is None or page is False:
                return page
        if end <= len(page):
            return page[offset:end]
        if len(page) < _WINDOW_PAGE_SIZE:
            return None
        following = pages.get(index + 1)
        if following is None:
            following = self._load_page(index + 1)
            if following is None or following is False:
                return following
        rest = end - _WINDOW_PAGE_SIZE
        if rest > len(following):
            return None
        return page[offset:] + following[:rest]

    def _unchanged(self) -> bool:
        """Whether the file still has its size and modification time from
        when it was opened; drops the window cache for good once not."""
        stat = os.fstat(self._fd)
        if stat.st_size == self._length and stat.st_mtime_ns == self._mtime_ns:
            return True
        self._window_cache = False
        self._pages.clear()
        return False

    def _load_page(self, index: int) -> bytes | bool | None:
        if not self._unchanged():
            return False
        position = index << _WINDOW_PAGE_SHIFT
        page = self._pread(_WINDOW_PAGE_SIZE, position)
        if len(page) < _WINDOW_PAGE_SIZE and position + len(page) < self._length:
            return None
        pages = self._pages
        if len(pages) >= _WINDOW_MAX_PAGES:
            del pages[next(iter(pages))]
        pages[index] = page
        return page

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

from __future__ import annotations

import logging
import tempfile
import threading
from collections.abc import Iterable
from typing import IO

from .memory_usage_setting import UNLIMITED, MemoryUsageSetting, StorageMode
from .random_access_read import RandomAccessRead

_log = logging.getLogger(__name__)

# Default 4 KiB page size — matches upstream ScratchFile's PAGE_SIZE.
DEFAULT_PAGE_SIZE: int = 4096

# Default spill threshold for MIXED mode when no explicit cap is given.
_DEFAULT_MIXED_SPILL_BYTES = 16 * 1024 * 1024  # 16 MiB

# Sentinel returned by dequeue_page() when the free-page queue is empty.
NO_FREE_PAGE: int = -1


class ScratchFile:
    """
    Page-based temporary storage allocator.

    Mirrors ``org.apache.pdfbox.io.ScratchFile`` (Apache PDFBox 3.0). Hands
    out fixed-size pages (default 4 KiB) backed by either RAM or a temp
    file, governed by a :class:`MemoryUsageSetting`:

    * ``MAIN_MEMORY_ONLY`` — all pages live in RAM (a list of ``bytearray``).
    * ``TEMP_FILE_ONLY``  — every page is written to a stdlib temp file.
    * ``MIXED``           — pages live in RAM until ``max_main_memory_bytes``
      is exhausted, after which new pages spill to a temp file.

    The page-oriented API matches upstream:

    * :meth:`get_new_page` allocates a fresh page index.
    * :meth:`read_page`    copies a page's bytes into a caller buffer.
    * :meth:`write_page`   stores bytes for a page index.
    * :meth:`mark_pages_as_free` returns a set of pages to the free pool
      so subsequent :meth:`get_new_page` calls reuse them.
    * :meth:`enqueue_page` / :meth:`dequeue_page` expose the free-page queue.

    Higher-level :class:`ScratchFileBuffer` instances created via
    :meth:`create_buffer` use this page API as their backing store, so
    closing the parent ``ScratchFile`` closes (and frees the pages of)
    every buffer it produced.
    """

    def __init__(
        self,
        setting: MemoryUsageSetting | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        self._setting = setting or MemoryUsageSetting.setup_main_memory_only()
        self._page_size = page_size
        self._lock = threading.RLock()

        # In-memory pages: list slot -> bytearray of length <= page_size.
        # None entries indicate the page is currently free / spilled.
        self._mem_pages: list[bytearray | None] = []

        # Page indices >= len(_mem_pages) live on the temp file.
        # Mapping: page_index -> file offset in self._tmp.
        self._file_pages: dict[int, int] = {}
        self._tmp: IO[bytes] | None = None
        self._tmp_next_offset: int = 0

        # Free-page LIFO queue (reused by get_new_page).
        self._free_pages: list[int] = []

        # Total pages ever allocated (highest index + 1, ignoring frees).
        self._page_count: int = 0

        # Buffers produced via create_buffer(); closed when ScratchFile closes.
        self._open_buffers: set[ScratchFileBuffer] = set()

        self._closed = False

        # Honour TEMP_FILE_ONLY by opening the temp file eagerly so failures
        # surface at construction time rather than on first allocation.
        if self._setting.mode is StorageMode.TEMP_FILE_ONLY:
            self._ensure_tmp()

    @classmethod
    def get_main_memory_only_instance(
        cls, max_main_memory_bytes: int | None = None
    ) -> ScratchFile:
        """
        Return a scratch file configured for main-memory-only storage.

        Mirrors upstream ``ScratchFile.getMainMemoryOnlyInstance()`` (line 150)
        and the overload ``ScratchFile.getMainMemoryOnlyInstance(long)`` (line
        173). When ``max_main_memory_bytes`` is ``None`` (or 0 / -1, matching
        upstream's "no restriction" sentinels) the returned instance has no
        main-memory cap. Otherwise the cap is honoured.
        """
        if max_main_memory_bytes is None or max_main_memory_bytes <= 0:
            return cls(MemoryUsageSetting.setup_main_memory_only())
        return cls(
            MemoryUsageSetting.setup_main_memory_only(
                max_main_memory_bytes=max_main_memory_bytes,
            )
        )

    # ----- properties -----

    @property
    def setting(self) -> MemoryUsageSetting:
        return self._setting

    @property
    def page_size(self) -> int:
        return self._page_size

    def get_page_size(self) -> int:
        """Upstream alias for :attr:`page_size`."""
        return self._page_size

    def is_closed(self) -> bool:
        return self._closed

    # ----- page-oriented API (upstream parity) -----

    def get_new_page(self) -> int:
        """
        Allocate and return the index of a fresh page.

        Reuses a previously freed page if one is queued; otherwise grows
        the page space. Newly allocated pages are zero-filled.
        """
        with self._lock:
            self._check_open()
            if self._free_pages:
                idx = self._free_pages.pop()
                self._reset_page(idx)
                return idx
            return self._allocate_new_page()

    def read_page(
        self,
        page_index: int,
        buf: bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> int:
        """
        Copy bytes from page ``page_index`` into ``buf``.

        ``length`` defaults to ``page_size``. Returns the number of bytes
        actually copied (always equal to ``length`` on success).
        """
        if length is None:
            length = self._page_size
        self._validate_page_io(page_index, buf, offset, length)
        with self._lock:
            self._check_open()
            data = self._fetch_page_bytes(page_index)
            view = memoryview(buf)[offset : offset + length]
            view[:length] = data[:length]
            return length

    def write_page(
        self,
        page_index: int,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        """
        Store ``length`` bytes from ``data[offset:offset+length]`` into
        page ``page_index``. ``length`` defaults to ``page_size``.
        """
        view = memoryview(data).cast("B")
        if length is None:
            length = self._page_size
        self._validate_page_io(page_index, view, offset, length)
        with self._lock:
            self._check_open()
            self._validate_page_index(page_index)
            payload = bytes(view[offset : offset + length])
            # Pad short writes with zeros so a page is always page_size long
            # in storage (matches upstream's fixed-page behavior).
            if length < self._page_size:
                payload = payload + bytes(self._page_size - length)
            self._store_page_bytes(page_index, payload)

    def mark_pages_as_free(self, indices: Iterable[int]) -> None:
        """
        Return the given pages to the free-page pool so subsequent
        :meth:`get_new_page` calls reuse them. Idempotent: indices that
        are already free or out-of-range are silently ignored (matches
        upstream's defensive behavior).
        """
        with self._lock:
            self._check_open()
            for idx in indices:
                if idx < 0 or idx >= self._page_count:
                    continue
                if idx in self._free_pages:
                    continue
                self._free_pages.append(idx)

    def enqueue_page(self, page: int) -> None:
        """Mark a single page as free (upstream API)."""
        self.mark_pages_as_free((page,))

    def dequeue_page(self) -> int:
        """
        Pop and return a previously freed page index, or :data:`NO_FREE_PAGE`
        (-1) if the free queue is empty. Mirrors upstream behaviour.
        """
        with self._lock:
            self._check_open()
            if not self._free_pages:
                return NO_FREE_PAGE
            return self._free_pages.pop()

    def get_main_memory_max_pages(self) -> int:
        """
        Configured cap on in-memory pages, derived from the setting's
        ``max_main_memory_bytes``. Returns -1 (unlimited) when no cap is
        set or in TEMP_FILE_ONLY mode (where main-memory pages aren't used).
        """
        if self._setting.mode is StorageMode.TEMP_FILE_ONLY:
            return 0
        cap = self._setting.max_main_memory_bytes
        if cap == UNLIMITED:
            return -1
        return cap // self._page_size

    def get_max_main_memory_bytes(self) -> int:
        """
        Spill-to-disk threshold in bytes. In MIXED mode without an explicit
        cap, returns the 16 MiB default. Otherwise returns the setting's
        configured ``max_main_memory_bytes`` (which may be ``UNLIMITED``).
        """
        if self._setting.mode is StorageMode.MIXED:
            if self._setting.max_main_memory_bytes == UNLIMITED:
                return _DEFAULT_MIXED_SPILL_BYTES
            return self._setting.max_main_memory_bytes
        return self._setting.max_main_memory_bytes

    def get_page_count(self) -> int:
        """Total pages allocated so far (free pages still count)."""
        return self._page_count

    # ----- buffer factory -----

    def create_buffer(self) -> ScratchFileBuffer:
        """
        Return a fresh :class:`ScratchFileBuffer` whose backing is this
        ScratchFile's page pool. Closing the buffer releases its pages.
        """
        with self._lock:
            self._check_open()
            buf = ScratchFileBuffer(self)
            self._open_buffers.add(buf)
            return buf

    def create_buffer_from_input(self, source: RandomAccessRead) -> ScratchFileBuffer:
        """Convenience: copy ``source`` (current pos -> end) into a new buffer."""
        buf = self.create_buffer()
        try:
            chunk = bytearray(self._page_size)
            while True:
                n = source.read_into(chunk)
                if n <= 0:
                    break
                buf.write_bytes(chunk, 0, n)
            buf.seek(0)
            return buf
        except Exception:
            try:
                buf.close()
            except Exception as close_exc:  # pragma: no cover - defensive cleanup
                _log.debug(
                    "ScratchFileBuffer close after failed input copy failed: %s",
                    close_exc,
                )
            raise

    def create_buffer_with_data(
        self, data: bytes | bytearray | memoryview
    ) -> ScratchFileBuffer:
        """
        Convenience: create a buffer pre-populated with ``data`` and seeked
        back to position 0.
        """
        buf = self.create_buffer()
        if len(data) > 0:
            buf.write_bytes(data)
        buf.seek(0)
        return buf

    def _buffer_closed(self, buf: ScratchFileBuffer) -> None:
        with self._lock:
            self._open_buffers.discard(buf)

    def remove_buffer(self, buf: ScratchFileBuffer) -> None:
        """
        Detach a buffer from this scratch file's owner set without closing it.

        Mirrors upstream package-private ``ScratchFile.removeBuffer`` (line 454)
        which is called by ``ScratchFileBuffer.close`` to drop itself from the
        owner's buffer list. Idempotent: removing an unknown buffer is a no-op.
        """
        with self._lock:
            self._open_buffers.discard(buf)

    # ----- lifecycle -----

    def close(self) -> None:
        """
        Close all outstanding buffers, drop in-memory pages, and delete the
        temp file (if any). Idempotent.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for buf in list(self._open_buffers):
                buf.close()
            self._open_buffers.clear()
            self._mem_pages.clear()
            self._file_pages.clear()
            self._free_pages.clear()
            if self._tmp is not None:
                try:
                    self._tmp.close()
                except OSError as exc:  # pragma: no cover - extremely unlikely
                    _log.debug("ScratchFile temp file close failed: %s", exc)
                self._tmp = None

    def __enter__(self) -> ScratchFile:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    # ----- internals -----

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed ScratchFile")

    def _init_pages(self) -> None:
        """
        Lazy page-pool initialisation hook.

        Mirrors upstream private ``ScratchFile.initPages`` (line 134) which
        allocates the ``inMemoryPages`` ``byte[][]`` and primes the
        ``freePages`` ``BitSet`` once on first use. The Python port already
        backs both pools with lazy lists/dicts that grow on demand
        (:attr:`_mem_pages`, :attr:`_file_pages`, :attr:`_free_pages`), so
        this is a no-op kept for parity-named call sites.
        """
        # Intentional no-op: lazy data structures self-initialise.
        return None

    def _enlarge(self) -> None:
        """
        Hook to grow the page pool when no free page is available.

        Mirrors upstream private ``ScratchFile.enlarge`` (line 236) which
        either extends the temp file by ``ENLARGE_PAGE_COUNT`` pages (when
        scratch-file usage is allowed) or doubles the in-memory ``byte[][]``
        and updates the ``freePages`` ``BitSet``. The Python port grows
        :attr:`_mem_pages` / :attr:`_file_pages` on each
        :meth:`_allocate_new_page` call, so the equivalent work happens
        inline; this method exists for parity-named call sites and is a
        no-op.
        """
        # Intentional no-op: _allocate_new_page() grows storage on demand.
        return None

    def check_closed(self) -> None:
        """
        Raise if this scratch file has already been closed.

        Mirrors upstream package-private ``ScratchFile.checkClosed`` (line 428).
        Provided as a parity-named helper; internal call sites use
        :meth:`_check_open` (which is the same predicate, kept for back-compat
        with the old internal name used elsewhere in this module).
        """
        self._check_open()

    def _validate_page_io(
        self,
        page_index: int,
        buf: bytes | bytearray | memoryview,
        offset: int,
        length: int,
    ) -> None:
        if length < 0:
            raise ValueError("length must be non-negative")
        if length > self._page_size:
            raise ValueError(
                f"length {length} exceeds page size {self._page_size}"
            )
        if offset < 0 or offset + length > len(buf):
            raise ValueError("offset/length out of range for buf")

    def _validate_page_index(self, idx: int) -> None:
        if idx < 0 or idx >= self._page_count:
            raise IndexError(f"page index {idx} out of range [0, {self._page_count})")

    def _ensure_tmp(self) -> IO[bytes]:
        if self._tmp is None:
            self._tmp = tempfile.TemporaryFile(  # noqa: SIM115
                mode="w+b",
                dir=self._setting.temp_dir,
            )
        return self._tmp

    def _allocate_new_page(self) -> int:
        idx = self._page_count
        self._page_count += 1
        if self._should_use_main_memory():
            self._mem_pages.append(bytearray(self._page_size))
        else:
            tmp = self._ensure_tmp()
            self._file_pages[idx] = self._tmp_next_offset
            tmp.seek(self._tmp_next_offset)
            tmp.write(bytes(self._page_size))
            self._tmp_next_offset += self._page_size
            # Pad the in-memory list so indices stay aligned.
            self._mem_pages.append(None)
        return idx

    def _reset_page(self, idx: int) -> None:
        # Zero the page so reused indices don't leak previous content.
        if idx < len(self._mem_pages) and self._mem_pages[idx] is not None:
            page = self._mem_pages[idx]
            assert page is not None  # for mypy
            page[:] = bytes(self._page_size)
        elif idx in self._file_pages:
            tmp = self._ensure_tmp()
            tmp.seek(self._file_pages[idx])
            tmp.write(bytes(self._page_size))

    def _should_use_main_memory(self) -> bool:
        mode = self._setting.mode
        if mode is StorageMode.MAIN_MEMORY_ONLY:
            return True
        if mode is StorageMode.TEMP_FILE_ONLY:
            return False
        # MIXED: stay in RAM until cap exhausted.
        cap = self.get_max_main_memory_bytes()
        if cap == UNLIMITED:
            return True
        used = sum(1 for p in self._mem_pages if p is not None) * self._page_size
        return used + self._page_size <= cap

    def _fetch_page_bytes(self, page_index: int) -> bytes:
        self._validate_page_index(page_index)
        if page_index < len(self._mem_pages) and self._mem_pages[page_index] is not None:
            return bytes(self._mem_pages[page_index])  # type: ignore[arg-type]
        # File-backed.
        if page_index not in self._file_pages:
            # Page exists but has never been written to (allocated only).
            return bytes(self._page_size)
        tmp = self._ensure_tmp()
        tmp.seek(self._file_pages[page_index])
        return tmp.read(self._page_size)

    def _store_page_bytes(self, page_index: int, payload: bytes) -> None:
        if (
            page_index < len(self._mem_pages)
            and self._mem_pages[page_index] is not None
        ):
            page = self._mem_pages[page_index]
            assert page is not None
            page[:] = payload
            return
        # File-backed: allocate the slot lazily for pages allocated when no
        # main-memory budget remained.
        tmp = self._ensure_tmp()
        if page_index in self._file_pages:
            offset = self._file_pages[page_index]
        else:
            offset = self._tmp_next_offset
            self._file_pages[page_index] = offset
            self._tmp_next_offset += self._page_size
        tmp.seek(offset)
        tmp.write(payload)


# Late import: ScratchFileBuffer references ScratchFile in its annotations.
from .scratch_file_buffer import ScratchFileBuffer  # noqa: E402

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "NO_FREE_PAGE",
    "ScratchFile",
    "ScratchFileBuffer",
]

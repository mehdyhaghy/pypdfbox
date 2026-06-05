from __future__ import annotations

from typing import TYPE_CHECKING

from .random_access_read import RandomAccessRead
from .random_access_write import RandomAccessWrite

if TYPE_CHECKING:
    from .scratch_file import ScratchFile


def _as_byte_view(data: bytes | bytearray | memoryview) -> memoryview:
    view = memoryview(data)
    try:
        return view.cast("B")
    except TypeError:
        return memoryview(bytes(view))


class ScratchFileBuffer(RandomAccessRead, RandomAccessWrite):
    """
    Random-access read+write buffer backed by a chain of fixed-size pages
    drawn from a parent :class:`ScratchFile`.

    Mirrors ``org.apache.pdfbox.io.ScratchFileBuffer`` (Apache PDFBox 3.0).
    Pages are allocated on demand as data is written; on close, all pages
    held by the buffer are returned to the parent's free-page pool via
    :meth:`ScratchFile.mark_pages_as_free`.

    Construction is delegated to :meth:`ScratchFile.create_buffer` — do not
    instantiate directly.
    """

    def __init__(self, owner: ScratchFile) -> None:
        self._owner = owner
        self._page_size = owner.page_size
        # Pages reserved by this buffer, in logical order.
        self._page_indices: list[int] = []
        self._position: int = 0
        self._length: int = 0
        # Lazy single-page scratch used to amortise byte-granular reads.
        self._scratch: bytearray = bytearray(self._page_size)
        self._closed = False
        # Eagerly allocate the first page (matches upstream ctor calling addPage()).
        self.add_page()

    # Resolve the diamond between RandomAccessRead and RandomAccessWrite.
    def __enter__(self) -> ScratchFileBuffer:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    # ----- upstream-named internal helpers (parity with Java ScratchFileBuffer) -----

    def check_closed(self) -> None:
        """
        Raise ``OSError`` if this buffer (or its parent ScratchFile) is closed.

        Mirrors upstream private ``checkClosed()`` (line 87). Kept under the
        upstream-equivalent name so Java porters can find it; it is *not*
        considered part of the public API.
        """
        if self._closed:
            raise OSError("Buffer already closed")
        if self._owner.is_closed():
            raise OSError("Scratch file already closed")

    # Backward-compat alias for the old internal name used by this module.
    _check_closed = check_closed
    _check_open = check_closed

    def add_page(self) -> None:
        """
        Allocate a new page from the parent ScratchFile and append it to
        this buffer's page chain.

        Mirrors upstream private ``addPage()`` (line 101).
        """
        self._page_indices.append(self._owner.get_new_page())

    def ensure_available_bytes_in_page(self, add_new_page_if_needed: bool) -> bool:
        """
        Ensure the current logical position has at least one writable / readable
        byte in its page. If the position lands exactly on a page boundary
        and we are at the end of the chain, allocate a new page when
        ``add_new_page_if_needed`` is True; otherwise return ``False``.

        Mirrors upstream private ``ensureAvailableBytesInPage(boolean)`` (line
        156). pypdfbox's read/write paths use random-access page lookups via
        :meth:`ScratchFile.read_page` / :meth:`write_page`, so this helper
        only needs to grow the page chain when writing past the tail.
        """
        page_idx_in_chain, off = divmod(self._position, self._page_size)
        if off == 0 and page_idx_in_chain >= len(self._page_indices):
            if add_new_page_if_needed:
                # Catch up with however many pages are needed (typically just one).
                while len(self._page_indices) <= page_idx_in_chain:
                    self.add_page()
                return True
            return False
        return True

    # ----- helpers -----

    def _ensure_capacity(self, needed_pages: int) -> None:
        while len(self._page_indices) < needed_pages:
            self.add_page()

    def _read_into_view(self, view: memoryview, length: int) -> int:
        """
        Read ``length`` bytes starting at ``self._position`` into ``view``.
        Returns bytes actually read, possibly less than ``length`` at EOF.
        """
        if length == 0:
            return 0
        remaining = self._length - self._position
        if remaining <= 0:
            return RandomAccessRead.EOF
        to_read = min(length, remaining)
        copied = 0
        while copied < to_read:
            page_idx_in_chain, off = divmod(self._position, self._page_size)
            page_id = self._page_indices[page_idx_in_chain]
            self._owner.read_page(page_id, self._scratch, 0, self._page_size)
            chunk = min(self._page_size - off, to_read - copied)
            view[copied : copied + chunk] = self._scratch[off : off + chunk]
            copied += chunk
            self._position += chunk
        return copied

    def _write_from_view(self, view: memoryview, length: int) -> None:
        if length == 0:
            return
        end_pos = self._position + length
        needed_pages = (end_pos + self._page_size - 1) // self._page_size
        self._ensure_capacity(needed_pages)
        written = 0
        while written < length:
            page_idx_in_chain, off = divmod(self._position, self._page_size)
            page_id = self._page_indices[page_idx_in_chain]
            chunk = min(self._page_size - off, length - written)
            # Read-modify-write the page so partial writes preserve neighbours.
            if off != 0 or chunk != self._page_size:
                self._owner.read_page(page_id, self._scratch, 0, self._page_size)
            self._scratch[off : off + chunk] = view[written : written + chunk]
            self._owner.write_page(page_id, self._scratch, 0, self._page_size)
            written += chunk
            self._position += chunk
        if self._position > self._length:
            self._length = self._position

    # ----- RandomAccessRead -----

    def read(self) -> int:
        self.check_closed()
        if self._position >= self._length:
            return self.EOF
        out = bytearray(1)
        n = self._read_into_view(memoryview(out), 1)
        return out[0] if n == 1 else self.EOF

    def read_into(
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        self.check_closed()
        if length is None:
            length = len(buf) - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > len(buf):
            raise ValueError("offset/length out of range for buf")
        if self._position >= self._length:
            return self.EOF if length > 0 else 0
        view = memoryview(buf)[offset : offset + length]
        return self._read_into_view(view, length)

    def get_position(self) -> int:
        self.check_closed()
        return self._position

    def seek(self, position: int) -> None:
        """
        Seek to ``position``.

        Mirrors upstream ``seek(long)`` (line 287):

        * Raises ``OSError`` (Java ``IOException``) on negative offsets.
        * Raises ``EOFError`` (Java ``EOFException``) when seeking past
          ``length()``. Matches PDFBOX-4756.
        * Raises ``OSError`` if the buffer (or its scratch file) is closed.
        """
        self.check_closed()
        if position < 0:
            raise OSError(f"Negative seek offset: {position}")
        if position > self._length:
            raise EOFError(
                f"seek({position}) past end of buffer (length={self._length})"
            )
        self._position = position

    def length(self) -> int:
        # Upstream parity: ScratchFileBuffer#length() (line 134) does NOT call
        # checkClosed() — it returns the cached size even after close(). Oracle
        # (RandomAccessWriteScratchSemanticsProbe: sbuf.lengthBufClosed=NO_THROW)
        # confirms no exception on a closed buffer. Do not add a close guard.
        return self._length

    def is_eof(self) -> bool:
        """
        ``True`` when the read position is at or past the end of the buffer.

        Mirrors upstream ``isEOF()`` (line 346). Overrides the cursor-peeking
        default in :class:`RandomAccessRead` so closed-buffer access raises
        the upstream-equivalent ``OSError`` instead of silently returning
        ``True`` via a swallowed read.
        """
        self.check_closed()
        return self._position >= self._length

    def is_empty(self) -> bool:
        """True when no bytes are stored (or after :meth:`clear`)."""
        self.check_closed()
        return self._length == 0

    def is_closed(self) -> bool:
        return self._closed

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        # Upstream: ScratchFileBuffer.createView throws UnsupportedOperationException.
        raise NotImplementedError(
            f"{type(self).__name__}.create_view isn't supported."
        )

    # ----- RandomAccessWrite -----

    def write(self, b: int) -> None:
        self.check_closed()
        if not 0 <= b <= 0xFF:
            raise ValueError("byte value must be in 0..255")
        # _write_from_view already grows the page chain via _ensure_capacity;
        # ensure_available_bytes_in_page exists for parity with upstream's
        # private helper, not as a precondition gate.
        self._write_from_view(memoryview(bytes((b,))), 1)

    def write_bytes(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        self.check_closed()
        view = _as_byte_view(data)
        if length is None:
            length = view.nbytes - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > view.nbytes:
            raise ValueError("offset/length out of range for data")
        self._write_from_view(view[offset : offset + length], length)

    def clear(self) -> None:
        self.check_closed()
        # Return owned pages; callers expect a fresh, empty buffer afterwards.
        if self._page_indices:
            self._owner.mark_pages_as_free(self._page_indices)
            self._page_indices.clear()
        self._position = 0
        self._length = 0
        # Upstream keeps the first page allocated after clear(); mirror that.
        self.add_page()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._page_indices and not self._owner.is_closed():
                self._owner.mark_pages_as_free(self._page_indices)
        finally:
            self._page_indices.clear()
            self._owner._buffer_closed(self)


__all__ = ["ScratchFileBuffer"]

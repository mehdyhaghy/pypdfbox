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

    # Resolve the diamond between RandomAccessRead and RandomAccessWrite.
    def __enter__(self) -> ScratchFileBuffer:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError("operation on closed ScratchFileBuffer")

    # ----- helpers -----

    def _ensure_capacity(self, needed_pages: int) -> None:
        while len(self._page_indices) < needed_pages:
            self._page_indices.append(self._owner.get_new_page())

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
        self._check_open()
        if self._position >= self._length:
            return self.EOF
        out = bytearray(1)
        n = self._read_into_view(memoryview(out), 1)
        return out[0] if n == 1 else self.EOF

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
        if self._position >= self._length:
            return self.EOF if length > 0 else 0
        view = memoryview(buf)[offset : offset + length]
        return self._read_into_view(view, length)

    def get_position(self) -> int:
        self._check_open()
        return self._position

    def seek(self, position: int) -> None:
        self._check_open()
        if position < 0:
            raise ValueError("position must be non-negative")
        # Mirror BytesIO permissiveness: seeking past end is allowed and
        # leaves length unchanged until a subsequent write.
        self._position = position

    def length(self) -> int:
        self._check_open()
        return self._length

    def is_empty(self) -> bool:
        """True when no bytes are stored (or after :meth:`clear`)."""
        self._check_open()
        return self._length == 0

    def is_closed(self) -> bool:
        return self._closed

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        # Upstream: ScratchFileBuffer does not support views.
        raise NotImplementedError("createView() not supported on ScratchFileBuffer")

    # ----- RandomAccessWrite -----

    def write(self, b: int) -> None:
        self._check_open()
        if not 0 <= b <= 0xFF:
            raise ValueError("byte value must be in 0..255")
        self._write_from_view(memoryview(bytes((b,))), 1)

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
        self._write_from_view(view[offset : offset + length], length)

    def clear(self) -> None:
        self._check_open()
        # Return owned pages; callers expect a fresh, empty buffer afterwards.
        if self._page_indices:
            self._owner.mark_pages_as_free(self._page_indices)
            self._page_indices.clear()
        self._position = 0
        self._length = 0

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

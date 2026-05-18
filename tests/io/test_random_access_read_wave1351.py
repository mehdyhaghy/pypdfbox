"""Coverage-boost (wave 1351) for :mod:`pypdfbox.io.random_access_read`.

Targets the ``RandomAccessRead.create_view`` default implementation
(lines 145-147 of ``random_access_read.py``) — every concrete subclass
shipped today overrides ``create_view``, so the ABC's default body
needs a tailor-made subclass that *doesn't* override to be exercised.
"""

from __future__ import annotations

from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_view import RandomAccessReadView


class _BarebonesRAR(RandomAccessRead):
    """Minimal :class:`RandomAccessRead` that does NOT override
    ``create_view`` — used to drive the ABC's default factory body
    (lines 145-147)."""

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        self._pos = 0
        self._closed = False

    def read(self) -> int:
        if self._pos >= len(self._data):
            return self.EOF
        b = self._data[self._pos]
        self._pos += 1
        return b

    def read_into(
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        if length is None:
            length = len(buf) - offset
        remaining = len(self._data) - self._pos
        if remaining <= 0:
            return -1
        n = min(length, remaining)
        buf[offset : offset + n] = self._data[self._pos : self._pos + n]
        self._pos += n
        return n

    def get_position(self) -> int:
        return self._pos

    def seek(self, position: int) -> None:
        self._pos = position

    def length(self) -> int:
        return len(self._data)

    def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed


def test_abc_create_view_returns_random_access_read_view() -> None:
    """The ABC's default ``create_view`` body imports
    :class:`RandomAccessReadView` lazily and wraps ``self`` — the
    returned view must round-trip the requested slice."""
    parent = _BarebonesRAR(b"abcdefghij")
    view = parent.create_view(2, 4)  # b"cdef"
    try:
        assert isinstance(view, RandomAccessReadView)
        assert view.length() == 4
        assert view.read() == ord("c")
        assert view.read() == ord("d")
        assert view.read() == ord("e")
        assert view.read() == ord("f")
        assert view.read() == RandomAccessRead.EOF
    finally:
        view.close()


def test_abc_create_view_with_zero_length_returns_empty_view() -> None:
    """Zero-length slice is a valid edge case — the default factory
    must still hand back a view (just one that's immediately at EOF)."""
    parent = _BarebonesRAR(b"abc")
    view = parent.create_view(1, 0)
    try:
        assert view.length() == 0
        assert view.read() == RandomAccessRead.EOF
    finally:
        view.close()

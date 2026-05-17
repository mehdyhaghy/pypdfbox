"""Wave 1332 coverage boost for ``SequenceRandomAccessRead``.

Targets the remaining uncovered branches in
``pypdfbox/io/sequence_random_access_read.py``:

* constructor input validation (``None`` reader_list, OSError on
  ``length()`` during materialisation);
* :meth:`check_closed` guard after :meth:`close`;
* zero-length ``read_into`` early return;
* EOF return path in ``read_into`` once ``available() == 0``;
* :meth:`seek` rejecting negative positions and clamping to the tail of
  the last source when the requested offset is past ``total_length``.
"""

from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer, SequenceRandomAccessRead
from pypdfbox.io.random_access_read import RandomAccessRead


def _seq(*parts: bytes) -> SequenceRandomAccessRead:
    return SequenceRandomAccessRead([RandomAccessReadBuffer(p) for p in parts])


def test_constructor_rejects_none() -> None:
    with pytest.raises(ValueError, match="Missing input parameter"):
        SequenceRandomAccessRead(None)  # type: ignore[arg-type]


class _RaisingLengthReader(RandomAccessRead):
    """Stub RAR that raises ``OSError`` from ``length()`` — used to drive
    both the materialisation-time and start/end-position-time OSError
    branches in the constructor."""

    def __init__(self) -> None:
        self._closed = False

    def length(self) -> int:
        raise OSError("synthetic length failure")

    def read(self) -> int:
        return -1

    def read_into(
        self, b: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        return -1

    def get_position(self) -> int:
        return 0

    def seek(self, position: int) -> None:  # pragma: no cover - not exercised
        return None

    def is_eof(self) -> bool:
        return True

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def create_view(self, start_position: int, length: int):  # pragma: no cover
        raise NotImplementedError

    def peek(self) -> int:
        return -1

    def rewind(self, n: int = 1) -> None:  # pragma: no cover
        return None


def test_constructor_wraps_length_oserror() -> None:
    """The ``OSError`` from ``length()`` during the filter step must be
    re-raised as ``ValueError("Problematic list")``."""
    with pytest.raises(ValueError, match="Problematic list"):
        SequenceRandomAccessRead([_RaisingLengthReader()])


class _LengthOnceThenRaiseReader(RandomAccessRead):
    """Returns a positive length on the first call (so the filter step
    keeps it) but raises on the second call (so the start/end-position
    loop trips the second OSError branch)."""

    def __init__(self) -> None:
        self._calls = 0
        self._closed = False

    def length(self) -> int:
        self._calls += 1
        if self._calls == 1:
            return 4
        raise OSError("second-call failure")

    def read(self) -> int:
        return -1

    def read_into(
        self, b: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        return -1

    def get_position(self) -> int:
        return 0

    def seek(self, position: int) -> None:  # pragma: no cover
        return None

    def is_eof(self) -> bool:
        return True

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def create_view(self, start_position: int, length: int):  # pragma: no cover
        raise NotImplementedError

    def peek(self) -> int:
        return -1

    def rewind(self, n: int = 1) -> None:  # pragma: no cover
        return None


def test_constructor_wraps_second_length_oserror() -> None:
    """Second-call OSError in the start/end-position loop also surfaces
    as ``ValueError("Problematic list")``."""
    with pytest.raises(ValueError, match="Problematic list"):
        SequenceRandomAccessRead([_LengthOnceThenRaiseReader()])


def test_check_closed_after_close() -> None:
    seq = _seq(b"abc")
    seq.close()
    assert seq.is_closed() is True
    with pytest.raises(OSError, match="already closed"):
        seq.check_closed()
    with pytest.raises(OSError, match="already closed"):
        seq.read()
    with pytest.raises(OSError, match="already closed"):
        seq.get_position()
    with pytest.raises(OSError, match="already closed"):
        seq.length()
    with pytest.raises(OSError, match="already closed"):
        seq.is_eof()
    with pytest.raises(OSError, match="already closed"):
        seq.seek(0)


def test_read_into_zero_length_returns_zero() -> None:
    """``length == 0`` must early-return ``0`` without touching the
    underlying source."""
    seq = _seq(b"abc")
    buf = bytearray(0)
    assert seq.read_into(buf, 0, 0) == 0


def test_read_into_at_eof_returns_eof_sentinel() -> None:
    """When the sequence is fully exhausted, ``read_into`` must return
    the EOF sentinel (``-1``)."""
    seq = _seq(b"ab")
    out = bytearray(2)
    assert seq.read_into(out) == 2
    # Position is now at total_length — available() == 0 path.
    assert seq.read_into(bytearray(4), 0, 4) == seq.EOF


def test_seek_negative_raises() -> None:
    seq = _seq(b"abc")
    with pytest.raises(OSError, match="Invalid position"):
        seq.seek(-1)


def test_seek_past_end_clamps_to_total_length() -> None:
    """Seeking past ``total_length`` parks the cursor at the end of the
    last source and reports EOF."""
    seq = _seq(b"abc", b"def")
    seq.seek(99)
    assert seq.is_eof() is True
    assert seq.get_position() == seq.length()


def test_create_view_not_supported() -> None:
    seq = _seq(b"abc")
    with pytest.raises(NotImplementedError, match="createView"):
        seq.create_view(0, 1)

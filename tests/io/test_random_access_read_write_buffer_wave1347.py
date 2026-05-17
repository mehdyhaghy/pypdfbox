"""Wave 1347 coverage boost for
``pypdfbox.io.random_access_read_write_buffer``.

Targets the residual constructor + ``write_bytes`` validation branches
not exercised by ``test_random_access_read_write_buffer_wave1281``:

- ``defined_chunk_size`` positive override (line 27) — confirms the
  constructor stores the override and that ``chunk_size`` updates.
- ``write_bytes`` with ``length=None`` (line 64) — default length
  derived from ``view.nbytes - offset``.
- ``write_bytes`` with negative ``length`` (line 66) — ``ValueError``.
- ``write_bytes`` with out-of-range ``offset`` / ``offset + length``
  (line 68) — ``ValueError``.

Pre-wave the module sat at 91.2 % (3 missing); this set takes it to
100 %.
"""

from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadWriteBuffer


# ---------------------------------------------------------------------------
# Constructor: ``defined_chunk_size`` positive override (line 27)
# ---------------------------------------------------------------------------
def test_defined_chunk_size_positive_overrides_default() -> None:
    buf = RandomAccessReadWriteBuffer(defined_chunk_size=8192)
    assert buf.chunk_size == 8192


def test_defined_chunk_size_zero_keeps_default() -> None:
    """``defined_chunk_size <= 0`` keeps the default — guards the
    ``> 0`` predicate on line 26."""
    buf = RandomAccessReadWriteBuffer(defined_chunk_size=0)
    assert buf.chunk_size == RandomAccessReadWriteBuffer.DEFAULT_CHUNK_SIZE_4KB


def test_defined_chunk_size_negative_keeps_default() -> None:
    buf = RandomAccessReadWriteBuffer(defined_chunk_size=-1)
    assert buf.chunk_size == RandomAccessReadWriteBuffer.DEFAULT_CHUNK_SIZE_4KB


def test_defined_chunk_size_none_keeps_default() -> None:
    buf = RandomAccessReadWriteBuffer(defined_chunk_size=None)
    assert buf.chunk_size == RandomAccessReadWriteBuffer.DEFAULT_CHUNK_SIZE_4KB


# ---------------------------------------------------------------------------
# ``write_bytes`` default-length branch (line 64)
# ---------------------------------------------------------------------------
def test_write_bytes_default_length_writes_remainder() -> None:
    """``length=None`` writes everything from ``offset`` to end of view."""
    buf = RandomAccessReadWriteBuffer()
    buf.write_bytes(b"hello world", offset=6)
    assert buf.length() == 5
    buf.seek(0)
    out = bytearray(5)
    buf.read_into(out)
    assert bytes(out) == b"world"


def test_write_bytes_default_length_zero_offset() -> None:
    """``offset=0, length=None`` writes the whole view."""
    buf = RandomAccessReadWriteBuffer()
    buf.write_bytes(b"hello world")
    assert buf.length() == 11


def test_write_bytes_default_length_with_memoryview() -> None:
    """Same default-length path but exercising a non-``bytes`` view
    (memoryview ``nbytes`` correctness)."""
    buf = RandomAccessReadWriteBuffer()
    buf.write_bytes(memoryview(bytearray(b"abcdef")), offset=2)
    assert buf.length() == 4


# ---------------------------------------------------------------------------
# ``write_bytes`` length validation (line 66)
# ---------------------------------------------------------------------------
def test_write_bytes_rejects_negative_length() -> None:
    buf = RandomAccessReadWriteBuffer()
    with pytest.raises(ValueError, match="length must be non-negative"):
        buf.write_bytes(b"abc", offset=0, length=-1)


# ---------------------------------------------------------------------------
# ``write_bytes`` offset/range validation (line 68)
# ---------------------------------------------------------------------------
def test_write_bytes_rejects_negative_offset() -> None:
    buf = RandomAccessReadWriteBuffer()
    with pytest.raises(ValueError, match="offset/length out of range"):
        buf.write_bytes(b"abc", offset=-1, length=2)


def test_write_bytes_rejects_offset_plus_length_out_of_range() -> None:
    buf = RandomAccessReadWriteBuffer()
    with pytest.raises(ValueError, match="offset/length out of range"):
        buf.write_bytes(b"abc", offset=1, length=5)


def test_write_bytes_offset_at_end_zero_length_is_ok() -> None:
    """Boundary: ``offset == nbytes`` with ``length == 0`` is valid."""
    buf = RandomAccessReadWriteBuffer()
    buf.write_bytes(b"abc", offset=3, length=0)
    assert buf.length() == 0

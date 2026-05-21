"""Wave 1367 — :class:`ScratchFileBuffer` multi-buffer + write semantics.

Targets behaviour that the existing :mod:`tests/io/test_scratch_file_buffer`
file leaves uncovered:

* Multiple buffers interleaving page allocations against a shared
  ScratchFile (free-page queue churn).
* Partial writes preserving neighbour bytes (read-modify-write path).
* Single-byte ``write(int)`` accepting only 0..255.
* ``write_bytes`` offset/length validation.
* ``clear`` keeps the buffer empty but immediately allocates one page
  (mirrors upstream's post-clear addPage()).
* ``seek`` past length raises ``EOFError``; negative offsets raise
  ``OSError``.
* ``create_view`` is unsupported.
* Closing the parent ScratchFile invalidates the buffer.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
from pypdfbox.io.scratch_file import DEFAULT_PAGE_SIZE, ScratchFile


def test_write_byte_accepts_only_unsigned_byte() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf:
        buf.write(0)
        buf.write(255)
        with pytest.raises(ValueError):
            buf.write(-1)
        with pytest.raises(ValueError):
            buf.write(256)


def test_write_bytes_validates_offset_length() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf:
        with pytest.raises(ValueError):
            buf.write_bytes(b"abc", 0, -1)
        with pytest.raises(ValueError):
            buf.write_bytes(b"abc", -1, 1)
        with pytest.raises(ValueError):
            buf.write_bytes(b"abc", 0, 5)


def test_partial_write_preserves_neighbours() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf:
        # First page of payload "AAA...AAA"
        buf.write_bytes(b"A" * DEFAULT_PAGE_SIZE)
        # Seek inside page 0 and overwrite a few middle bytes.
        buf.seek(100)
        buf.write_bytes(b"ZZZ")
        buf.seek(0)
        out = bytearray(DEFAULT_PAGE_SIZE)
        buf.read_into(out)
        assert bytes(out[:100]) == b"A" * 100
        assert bytes(out[100:103]) == b"ZZZ"
        assert bytes(out[103:]) == b"A" * (DEFAULT_PAGE_SIZE - 103)


def test_write_spans_multiple_pages() -> None:
    payload = bytes(range(256)) * 80  # ~20 KiB, multi-page
    with ScratchFile() as sf, sf.create_buffer() as buf:
        buf.write_bytes(payload)
        assert buf.length() == len(payload)
        buf.seek(0)
        out = bytearray(len(payload))
        buf.read_into(out)
        assert bytes(out) == payload


def test_seek_past_length_raises_eof_error() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf:
        buf.write_bytes(b"abc")
        with pytest.raises(EOFError):
            buf.seek(99)


def test_seek_negative_raises_oserror() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf, pytest.raises(OSError):
        buf.seek(-1)


def test_create_view_unsupported() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf, pytest.raises(NotImplementedError):
        buf.create_view(0, 2)


def test_clear_resets_state_but_keeps_one_page() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf:
        buf.write_bytes(b"abc" * 4096)
        assert buf.length() > 0
        buf.clear()
        assert buf.is_empty() is True
        assert buf.length() == 0
        assert buf.get_position() == 0
        # Still usable.
        buf.write_bytes(b"new")
        assert buf.length() == 3


def test_close_returns_pages_to_owner_free_pool() -> None:
    sf = ScratchFile()
    try:
        buf = sf.create_buffer()
        buf.write_bytes(b"x" * (DEFAULT_PAGE_SIZE * 3))
        page_count_before_close = sf.get_page_count()
        buf.close()
        # Pages are returned to the free pool, not de-allocated.
        assert sf.get_page_count() == page_count_before_close
        # And get_new_page must pop a freed one.
        idx = sf.get_new_page()
        assert idx < page_count_before_close
    finally:
        sf.close()


def test_close_idempotent() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.close()
        buf.close()  # idempotent
        assert buf.is_closed() is True
        with pytest.raises(OSError):
            buf.read()
        with pytest.raises(OSError):
            buf.write(0)


def test_parent_close_invalidates_buffer() -> None:
    sf = ScratchFile()
    buf = sf.create_buffer()
    sf.close()
    # Buffer marked closed via the parent's close fan-out.
    assert buf.is_closed() is True


def test_interleaved_buffers_share_free_pool() -> None:
    """Two buffers churning through write/clear cycles must coexist
    without page-index aliasing."""
    with ScratchFile() as sf:
        a = sf.create_buffer()
        b = sf.create_buffer()
        try:
            a.write_bytes(b"A" * (DEFAULT_PAGE_SIZE * 2))
            b.write_bytes(b"B" * (DEFAULT_PAGE_SIZE * 2))
            # Clear A — its pages become free.
            a.clear()
            # New write to A reuses some free page.
            a.write_bytes(b"a" * 10)
            # B's content must be untouched.
            b.seek(0)
            out = bytearray(DEFAULT_PAGE_SIZE * 2)
            b.read_into(out)
            assert bytes(out) == b"B" * (DEFAULT_PAGE_SIZE * 2)
            # A's new content readable too.
            a.seek(0)
            out2 = bytearray(10)
            a.read_into(out2)
            assert bytes(out2) == b"a" * 10
        finally:
            a.close()
            b.close()


def test_read_returns_unsigned_byte_at_position() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf:
        buf.write_bytes(bytes([0x00, 0x7F, 0x80, 0xFF]))
        buf.seek(0)
        assert buf.read() == 0x00
        assert buf.read() == 0x7F
        assert buf.read() == 0x80
        assert buf.read() == 0xFF
        assert buf.read() == buf.EOF


def test_read_into_negative_length_raises() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf, pytest.raises(ValueError):
        buf.read_into(bytearray(4), 0, -1)


def test_read_into_bad_offset_raises() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf, pytest.raises(ValueError):
        buf.read_into(bytearray(2), 0, 3)


def test_temp_file_only_storage_works() -> None:
    sf = ScratchFile(MemoryUsageSetting.setup_temp_file_only())
    try:
        buf = sf.create_buffer()
        try:
            buf.write_bytes(b"temp-file backed")
            buf.seek(0)
            out = bytearray(16)
            buf.read_into(out)
            assert bytes(out) == b"temp-file backed"
        finally:
            buf.close()
    finally:
        sf.close()


def test_ensure_available_bytes_in_page_grows_chain() -> None:
    with ScratchFile() as sf, sf.create_buffer() as buf:
        # Position at start; needs page.
        assert buf.ensure_available_bytes_in_page(add_new_page_if_needed=True) is True
        # Now write past the first page boundary to force growth.
        buf.write_bytes(b"x" * DEFAULT_PAGE_SIZE)
        # At the boundary, with add_new_page_if_needed=False, must return False.
        assert (
            buf.ensure_available_bytes_in_page(add_new_page_if_needed=False) is False
        )

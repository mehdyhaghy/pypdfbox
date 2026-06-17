"""
Hand-written tests for ``pypdfbox.io.ScratchFileBuffer``.

ScratchFileBuffer is now backed by the parent ScratchFile's page pool, so
these tests exercise the page-spanning read/write path, partial-page
writes, and free-page reuse on close/clear.
"""

from __future__ import annotations

import pytest

from pypdfbox.io import (
    DEFAULT_PAGE_SIZE,
    MemoryUsageSetting,
    ScratchFile,
    ScratchFileBuffer,
)


def test_buffer_is_random_access_read_and_write_subclass() -> None:
    from pypdfbox.io import RandomAccessRead, RandomAccessWrite

    with ScratchFile() as sf:
        buf = sf.create_buffer()
        assert isinstance(buf, ScratchFileBuffer)
        assert isinstance(buf, RandomAccessRead)
        assert isinstance(buf, RandomAccessWrite)


def test_single_byte_round_trip() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.write(0x41)
        buf.write(0x42)
        buf.seek(0)
        assert buf.read() == 0x41
        assert buf.read() == 0x42
        assert buf.read() == buf.EOF


def test_write_spans_multiple_pages() -> None:
    # Force a small page size to make multi-page traversal cheap to assert.
    with ScratchFile(page_size=16) as sf:
        buf = sf.create_buffer()
        payload = bytes(range(50))  # 50 bytes => 4 pages of 16
        buf.write_bytes(payload)
        assert buf.length() == 50
        buf.seek(0)
        out = bytearray(50)
        assert buf.read_into(out) == 50
        assert bytes(out) == payload


def test_partial_read_at_eof_returns_short_count() -> None:
    with ScratchFile(page_size=8) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"abcde")  # 5 bytes
        buf.seek(0)
        out = bytearray(10)
        assert buf.read_into(out) == 5
        assert bytes(out[:5]) == b"abcde"
        # Subsequent read at EOF is signalled.
        assert buf.read_into(out) == buf.EOF


def test_seek_then_overwrite_preserves_neighbour_bytes() -> None:
    with ScratchFile(page_size=16) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"X" * 32)
        buf.seek(10)
        buf.write_bytes(b"abc")  # straddles within one page
        buf.seek(0)
        out = bytearray(32)
        buf.read_into(out)
        assert bytes(out[:10]) == b"X" * 10
        assert bytes(out[10:13]) == b"abc"
        assert bytes(out[13:]) == b"X" * 19


def test_seek_then_overwrite_across_page_boundary() -> None:
    with ScratchFile(page_size=8) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"X" * 24)  # 3 pages
        buf.seek(6)  # position straddles pages 0 and 1
        buf.write_bytes(b"abcd")
        buf.seek(0)
        out = bytearray(24)
        buf.read_into(out)
        assert bytes(out) == b"XXXXXX" + b"abcd" + b"X" * 14


def test_clear_returns_pages_to_free_pool() -> None:
    with ScratchFile(page_size=8) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"y" * 20)
        pages_before_clear = sf.get_page_count()
        assert pages_before_clear >= 3
        buf.clear()
        assert buf.length() == 0
        assert buf.get_position() == 0
        # Writing again after clear should reuse freed pages, not grow.
        buf.write_bytes(b"z" * 8)
        assert sf.get_page_count() == pages_before_clear


def test_close_returns_pages_to_owner_free_pool() -> None:
    with ScratchFile(page_size=16) as sf:
        a = sf.create_buffer()
        a.write_bytes(b"q" * 32)  # uses 2 pages
        a.close()
        # Second buffer should reuse the freed pages: total page count stays at 2.
        b = sf.create_buffer()
        b.write_bytes(b"r" * 32)
        assert sf.get_page_count() == 2


def test_close_idempotent() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.close()
        buf.close()  # must not raise
        assert buf.is_closed()


def test_operations_after_close_raise() -> None:
    # Upstream raises IOException on every method when the buffer is closed.
    # We map IOException → OSError (per the project's test-porting conventions).
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.close()
        with pytest.raises(OSError):
            buf.write(0x00)
        with pytest.raises(OSError):
            buf.write_bytes(b"x")
        with pytest.raises(OSError):
            buf.seek(0)
        with pytest.raises(OSError):
            buf.read()
        with pytest.raises(OSError):
            buf.read_into(bytearray(1))


def test_negative_seek_raises() -> None:
    # Upstream throws IOException("Negative seek offset: ...") → OSError.
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        with pytest.raises(OSError):
            buf.seek(-1)


def test_seek_past_length_raises_eof_error() -> None:
    # Upstream throws EOFException when seeking past length() (PDFBOX-4756).
    with ScratchFile(page_size=8) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"hello")
        # Seeking exactly to length is allowed (it's the EOF cursor position).
        buf.seek(buf.length())
        with pytest.raises(EOFError):
            buf.seek(buf.length() + 1)


def test_seek_to_length_then_read_returns_eof() -> None:
    with ScratchFile(page_size=8) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"abc")
        buf.seek(buf.length())
        assert buf.is_eof()
        assert buf.read() == buf.EOF


def test_buffer_starts_with_one_page_eagerly_allocated() -> None:
    # Upstream ctor calls addPage(); our buffer mirrors that so a fresh
    # buffer already owns one page from the parent ScratchFile.
    with ScratchFile(page_size=16) as sf:
        before = sf.get_page_count()
        sf.create_buffer()
        assert sf.get_page_count() == before + 1


def test_clear_keeps_one_page_allocated() -> None:
    # Upstream's clear() frees all pages except the first; we mirror that
    # by freeing everything and re-allocating one page on top of the freed pool.
    with ScratchFile(page_size=8) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"y" * 24)  # 3 pages
        buf.clear()
        # length/position reset, and the buffer still has one (reused) page.
        assert buf.length() == 0
        assert buf.get_position() == 0
        assert len(buf._page_indices) == 1


def test_check_closed_raises_after_close() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.close()
        with pytest.raises(OSError, match="closed"):
            buf.check_closed()


def test_check_closed_raises_when_owner_closed() -> None:
    sf = ScratchFile()
    buf = sf.create_buffer()
    sf.close()
    with pytest.raises(OSError, match="closed"):
        buf.check_closed()


def test_ensure_available_bytes_in_page_grows_chain_when_allowed() -> None:
    with ScratchFile(page_size=8) as sf:
        buf = sf.create_buffer()
        # Position at the boundary of the (only) eagerly-allocated page.
        buf._position = 8
        # Without permission to grow, return False (we'd be at end-of-chain).
        assert buf.ensure_available_bytes_in_page(False) is False
        # With permission, a new page is appended.
        before = len(buf._page_indices)
        assert buf.ensure_available_bytes_in_page(True) is True
        assert len(buf._page_indices) == before + 1


def test_negative_byte_value_raises() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        with pytest.raises(ValueError):
            buf.write(-1)
        with pytest.raises(ValueError):
            buf.write(256)


def test_create_view_not_supported() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"abcdef")
        with pytest.raises(NotImplementedError):
            buf.create_view(0, 3)


def test_default_page_size_used_when_unspecified() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        # Write exactly one default-sized page worth and a single trailing byte.
        buf.write_bytes(bytes(DEFAULT_PAGE_SIZE))
        buf.write_bytes(b"!")
        assert buf.length() == DEFAULT_PAGE_SIZE + 1
        assert sf.get_page_count() == 2


def test_temp_file_only_buffer_round_trip() -> None:
    with ScratchFile(MemoryUsageSetting.setup_temp_file_only(), page_size=32) as sf:
        buf = sf.create_buffer()
        payload = b"on disk pages " * 10
        buf.write_bytes(payload)
        buf.seek(0)
        out = bytearray(len(payload))
        assert buf.read_into(out) == len(payload)
        assert bytes(out) == payload


def test_mixed_mode_spills_to_disk_after_threshold() -> None:
    # 3 pages allowed in RAM, then spill.
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=3 * 16)
    with ScratchFile(setting, page_size=16) as sf:
        buf = sf.create_buffer()
        # 6 pages: pages 0..2 in RAM, 3..5 on disk.
        payload = bytes(range(96))
        buf.write_bytes(payload)
        buf.seek(0)
        out = bytearray(96)
        assert buf.read_into(out) == 96
        assert bytes(out) == payload


def test_multiple_buffers_have_independent_pages() -> None:
    with ScratchFile(page_size=16) as sf:
        a = sf.create_buffer()
        b = sf.create_buffer()
        a.write_bytes(b"AAAAAAAAAAAAAAAA")
        b.write_bytes(b"BBBBBBBBBBBBBBBB")
        a.seek(0)
        b.seek(0)
        out_a = bytearray(16)
        out_b = bytearray(16)
        a.read_into(out_a)
        b.read_into(out_b)
        assert bytes(out_a) == b"A" * 16
        assert bytes(out_b) == b"B" * 16

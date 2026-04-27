"""
Ported from
io/src/test/java/org/apache/pdfbox/io/ScratchFileTest.java
(Apache PDFBox 3.0).

Upstream's ScratchFileTest exercises page allocation, free-page reuse,
and the MemoryUsageSetting policy. The pypdfbox port retains the same
public surface (``get_new_page``, ``read_page``, ``write_page``,
``mark_pages_as_free``, ``enqueue_page``/``dequeue_page``); a few
upstream tests poking at private fields are skipped with comments.
"""

from __future__ import annotations

import pytest

from pypdfbox.io import (
    DEFAULT_PAGE_SIZE,
    NO_FREE_PAGE,
    MemoryUsageSetting,
    ScratchFile,
)


def test_scratch_file_main_memory_only() -> None:
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as sf:
        assert sf.get_page_size() == DEFAULT_PAGE_SIZE
        idx = sf.get_new_page()
        assert idx == 0
        # Round-trip a full page.
        payload = bytes((i & 0xFF) for i in range(DEFAULT_PAGE_SIZE))
        sf.write_page(idx, payload)
        out = bytearray(DEFAULT_PAGE_SIZE)
        sf.read_page(idx, out)
        assert bytes(out) == payload


def test_scratch_file_temp_file_only() -> None:
    with ScratchFile(MemoryUsageSetting.setup_temp_file_only()) as sf:
        idx = sf.get_new_page()
        sf.write_page(idx, b"\xab" * DEFAULT_PAGE_SIZE)
        out = bytearray(DEFAULT_PAGE_SIZE)
        sf.read_page(idx, out)
        assert bytes(out) == b"\xab" * DEFAULT_PAGE_SIZE


def test_scratch_file_mixed_below_threshold_stays_in_memory() -> None:
    setting = MemoryUsageSetting.setup_mixed(
        max_main_memory_bytes=DEFAULT_PAGE_SIZE * 4,
    )
    with ScratchFile(setting) as sf:
        for _ in range(3):
            sf.get_new_page()
        # We've allocated 3 pages; cap allows 4. All should fit in memory.
        # (We can't introspect storage from outside, but the round-trip must work.)
        for i in range(3):
            sf.write_page(i, bytes([i]) * DEFAULT_PAGE_SIZE)
        for i in range(3):
            out = bytearray(DEFAULT_PAGE_SIZE)
            sf.read_page(i, out)
            assert bytes(out) == bytes([i]) * DEFAULT_PAGE_SIZE


def test_scratch_file_mixed_spills_above_threshold() -> None:
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=DEFAULT_PAGE_SIZE)
    with ScratchFile(setting) as sf:
        for _ in range(4):
            sf.get_new_page()
        # 4 pages, only 1 page worth of RAM allowed -> 3 must spill.
        for i in range(4):
            sf.write_page(i, bytes([i]) * DEFAULT_PAGE_SIZE)
        for i in range(4):
            out = bytearray(DEFAULT_PAGE_SIZE)
            sf.read_page(i, out)
            assert bytes(out) == bytes([i]) * DEFAULT_PAGE_SIZE


def test_get_new_page_increments_index() -> None:
    with ScratchFile() as sf:
        a = sf.get_new_page()
        b = sf.get_new_page()
        c = sf.get_new_page()
        assert a == 0
        assert b == 1
        assert c == 2


def test_mark_pages_as_free_then_reuse() -> None:
    with ScratchFile() as sf:
        i0 = sf.get_new_page()
        i1 = sf.get_new_page()
        i2 = sf.get_new_page()
        sf.mark_pages_as_free([i0, i2])
        # Two new allocations should reuse the freed slots (LIFO order).
        next_a = sf.get_new_page()
        next_b = sf.get_new_page()
        assert {next_a, next_b} == {i0, i2}
        # Page count should not have grown.
        assert sf.get_page_count() == 3
        # And one untouched live page remains.
        assert i1 == 1


def test_enqueue_dequeue_round_trip() -> None:
    with ScratchFile() as sf:
        idx = sf.get_new_page()
        sf.enqueue_page(idx)
        assert sf.dequeue_page() == idx
        assert sf.dequeue_page() == NO_FREE_PAGE


def test_close_then_get_new_page_throws() -> None:
    sf = ScratchFile()
    sf.close()
    with pytest.raises(ValueError):
        sf.get_new_page()


def test_close_is_idempotent() -> None:
    sf = ScratchFile()
    sf.close()
    sf.close()  # second close must not raise
    assert sf.is_closed()


def test_create_buffer_reads_back_what_was_written() -> None:
    # Loosely mirrors upstream's basic buffer-via-scratchfile round-trip test.
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        payload = b"the quick brown fox jumps over the lazy dog"
        buf.write_bytes(payload)
        buf.seek(0)
        out = bytearray(len(payload))
        assert buf.read_into(out) == len(payload)
        assert bytes(out) == payload


def test_buffers_closed_when_scratch_file_closes() -> None:
    sf = ScratchFile()
    a = sf.create_buffer()
    b = sf.create_buffer()
    sf.close()
    assert a.is_closed()
    assert b.is_closed()


# Skipped: upstream tests that poke at private free-page-list mechanics
# (``ScratchFile.freePages`` field) are not reproducible without the same
# internal layout; observable behavior is covered above.

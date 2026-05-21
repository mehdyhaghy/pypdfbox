"""Wave 1367 — :class:`ScratchFile` page allocator stress + edge cases.

Targets branches that existing waves (299/680/720/1275) leave uncovered:
* Free-page LIFO order and dedup-on-enqueue.
* ``mark_pages_as_free`` ignores out-of-range / duplicate indices.
* ``get_main_memory_max_pages`` mode/cap matrix.
* ``get_max_main_memory_bytes`` MIXED-without-cap default branch.
* MIXED-mode rationing — explicit cap forces spill to temp file.
* ``create_buffer_from_input`` round-trip and failure cleanup.
* ``create_buffer_with_data`` empty + non-empty paths.
* ``write_page`` short payload zero-padded to page size.
* ``remove_buffer`` idempotent vs unknown buffer.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.memory_usage_setting import (
    UNLIMITED,
    MemoryUsageSetting,
    StorageMode,
)
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.scratch_file import (
    DEFAULT_PAGE_SIZE,
    NO_FREE_PAGE,
    ScratchFile,
)


def test_get_new_page_assigns_sequential_indices() -> None:
    with ScratchFile() as sf:
        idxs = [sf.get_new_page() for _ in range(5)]
        assert idxs == [0, 1, 2, 3, 4]
        assert sf.get_page_count() == 5


def test_free_pages_reused_in_lifo_order() -> None:
    with ScratchFile() as sf:
        a, b, c = (sf.get_new_page() for _ in range(3))
        sf.mark_pages_as_free([a, b])
        # LIFO: most recently freed page comes out first.
        assert sf.get_new_page() == b
        assert sf.get_new_page() == a
        # No more free pages -> fresh index.
        assert sf.get_new_page() == c + 1


def test_reused_page_is_zeroed() -> None:
    with ScratchFile() as sf:
        page = sf.get_new_page()
        sf.write_page(page, b"\xff" * DEFAULT_PAGE_SIZE)
        sf.mark_pages_as_free([page])
        reused = sf.get_new_page()
        assert reused == page
        out = bytearray(DEFAULT_PAGE_SIZE)
        sf.read_page(reused, out)
        assert bytes(out) == bytes(DEFAULT_PAGE_SIZE)


def test_mark_pages_as_free_ignores_unknown_and_dup() -> None:
    with ScratchFile() as sf:
        p = sf.get_new_page()
        # Out of range, negative, and duplicate are silently dropped.
        sf.mark_pages_as_free([-1, 999, p, p])
        assert sf.dequeue_page() == p
        assert sf.dequeue_page() == NO_FREE_PAGE


def test_enqueue_page_round_trip() -> None:
    with ScratchFile() as sf:
        p = sf.get_new_page()
        sf.enqueue_page(p)
        assert sf.dequeue_page() == p


def test_dequeue_empty_returns_sentinel() -> None:
    with ScratchFile() as sf:
        assert sf.dequeue_page() == NO_FREE_PAGE


def test_get_main_memory_max_pages_unlimited() -> None:
    sf = ScratchFile()
    try:
        assert sf.get_main_memory_max_pages() == -1
    finally:
        sf.close()


def test_get_main_memory_max_pages_capped() -> None:
    setting = MemoryUsageSetting.setup_main_memory_only(
        max_main_memory_bytes=DEFAULT_PAGE_SIZE * 4,
    )
    sf = ScratchFile(setting)
    try:
        assert sf.get_main_memory_max_pages() == 4
    finally:
        sf.close()


def test_get_main_memory_max_pages_temp_file_only_is_zero() -> None:
    sf = ScratchFile(MemoryUsageSetting.setup_temp_file_only())
    try:
        assert sf.get_main_memory_max_pages() == 0
    finally:
        sf.close()


def test_get_max_main_memory_bytes_mixed_default() -> None:
    # Construct a MIXED setting with UNLIMITED cap directly (the public
    # ``setup_mixed`` factory rejects negative caps; we exercise the
    # default-branch in ScratchFile.get_max_main_memory_bytes() that maps
    # UNLIMITED -> 16 MiB).
    setting = MemoryUsageSetting(
        mode=StorageMode.MIXED,
        max_main_memory_bytes=UNLIMITED,
        max_storage_bytes=UNLIMITED,
    )
    sf = ScratchFile(setting)
    try:
        # MIXED with UNLIMITED cap falls back to the 16 MiB default.
        assert sf.get_max_main_memory_bytes() == 16 * 1024 * 1024
    finally:
        sf.close()


def test_mixed_mode_spills_to_temp_after_cap() -> None:
    # Cap = 1 page. After the first allocation, subsequent ones should
    # be temp-file backed.
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=DEFAULT_PAGE_SIZE)
    sf = ScratchFile(setting)
    try:
        first = sf.get_new_page()
        sf.write_page(first, b"A" * DEFAULT_PAGE_SIZE)
        second = sf.get_new_page()
        sf.write_page(second, b"B" * DEFAULT_PAGE_SIZE)
        # First page lives in RAM, second in temp; both still readable.
        out_a = bytearray(DEFAULT_PAGE_SIZE)
        out_b = bytearray(DEFAULT_PAGE_SIZE)
        sf.read_page(first, out_a)
        sf.read_page(second, out_b)
        assert bytes(out_a) == b"A" * DEFAULT_PAGE_SIZE
        assert bytes(out_b) == b"B" * DEFAULT_PAGE_SIZE
        # Confirm second really went to the temp store.
        assert sf._mem_pages[second] is None
        assert second in sf._file_pages
    finally:
        sf.close()


def test_write_page_short_payload_zero_pads() -> None:
    with ScratchFile() as sf:
        p = sf.get_new_page()
        sf.write_page(p, b"hello", 0, 5)
        out = bytearray(DEFAULT_PAGE_SIZE)
        sf.read_page(p, out)
        assert bytes(out[:5]) == b"hello"
        # Remaining must be zero.
        assert bytes(out[5:]) == bytes(DEFAULT_PAGE_SIZE - 5)


def test_write_page_validates_length_exceeds_page_size() -> None:
    with ScratchFile() as sf:
        p = sf.get_new_page()
        with pytest.raises(ValueError):
            sf.write_page(p, b"x" * DEFAULT_PAGE_SIZE, 0, DEFAULT_PAGE_SIZE + 1)


def test_write_page_validates_bad_offset() -> None:
    with ScratchFile() as sf:
        p = sf.get_new_page()
        with pytest.raises(ValueError):
            sf.write_page(p, b"abc", -1, 1)
        with pytest.raises(ValueError):
            sf.write_page(p, b"abc", 0, -1)


def test_read_page_validates_bad_offset() -> None:
    with ScratchFile() as sf:
        p = sf.get_new_page()
        out = bytearray(2)
        with pytest.raises(ValueError):
            sf.read_page(p, out, 0, 3)  # length > buf
        with pytest.raises(ValueError):
            sf.read_page(p, out, -1, 1)


def test_read_page_unknown_index_raises() -> None:
    with ScratchFile() as sf:
        out = bytearray(DEFAULT_PAGE_SIZE)
        with pytest.raises(IndexError):
            sf.read_page(99, out)


def test_create_buffer_from_input_round_trip() -> None:
    payload = b"hello world " * 1024  # ~12 KiB, spans pages
    with ScratchFile() as sf:
        src = RandomAccessReadBuffer(payload)
        buf = sf.create_buffer_from_input(src)
        try:
            assert buf.length() == len(payload)
            assert buf.get_position() == 0
            data = bytearray(len(payload))
            buf.read_into(data)
            assert bytes(data) == payload
        finally:
            buf.close()


def test_create_buffer_from_input_failure_closes_buffer() -> None:
    class BlowsUp(RandomAccessReadBuffer):
        def read_into(  # type: ignore[override]
            self, buf: bytearray, offset: int = 0, length: int | None = None
        ) -> int:
            raise OSError("boom")

    src = BlowsUp(b"x" * 16)
    sf = ScratchFile()
    try:
        with pytest.raises(OSError):
            sf.create_buffer_from_input(src)
        # The half-created buffer must have been removed from the owner set.
        assert not sf._open_buffers
    finally:
        sf.close()


def test_create_buffer_with_data_empty() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer_with_data(b"")
        try:
            assert buf.length() == 0
            assert buf.get_position() == 0
        finally:
            buf.close()


def test_create_buffer_with_data_seeks_to_zero() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer_with_data(b"abcdef")
        try:
            assert buf.length() == 6
            assert buf.get_position() == 0
            out = bytearray(6)
            buf.read_into(out)
            assert bytes(out) == b"abcdef"
        finally:
            buf.close()


def test_remove_buffer_unknown_is_noop() -> None:
    sf = ScratchFile()
    try:
        # An unrelated buffer was never tracked; remove_buffer must not raise.
        other_sf = ScratchFile()
        try:
            other_buf = other_sf.create_buffer()
            try:
                sf.remove_buffer(other_buf)  # silent no-op
            finally:
                other_buf.close()
        finally:
            other_sf.close()
    finally:
        sf.close()


def test_close_idempotent() -> None:
    sf = ScratchFile()
    sf.close()
    sf.close()  # idempotent
    assert sf.is_closed() is True
    with pytest.raises(ValueError):
        sf.get_new_page()
    with pytest.raises(ValueError):
        sf.dequeue_page()
    with pytest.raises(ValueError):
        sf.create_buffer()


def test_close_propagates_to_open_buffers() -> None:
    sf = ScratchFile()
    buf = sf.create_buffer()
    sf.close()
    assert buf.is_closed() is True


def test_page_size_zero_or_negative_rejected() -> None:
    with pytest.raises(ValueError):
        ScratchFile(page_size=0)
    with pytest.raises(ValueError):
        ScratchFile(page_size=-4)


def test_get_main_memory_only_instance_factory_paths() -> None:
    sf_unlimited = ScratchFile.get_main_memory_only_instance()
    try:
        assert sf_unlimited.setting.mode is StorageMode.MAIN_MEMORY_ONLY
        assert sf_unlimited.setting.max_main_memory_bytes == UNLIMITED
    finally:
        sf_unlimited.close()

    # Negative cap is treated as unlimited (matches upstream sentinel handling).
    sf_neg = ScratchFile.get_main_memory_only_instance(-1)
    try:
        assert sf_neg.setting.max_main_memory_bytes == UNLIMITED
    finally:
        sf_neg.close()

    sf_capped = ScratchFile.get_main_memory_only_instance(DEFAULT_PAGE_SIZE * 8)
    try:
        assert sf_capped.setting.max_main_memory_bytes == DEFAULT_PAGE_SIZE * 8
    finally:
        sf_capped.close()


def test_init_pages_and_enlarge_are_noop_parity_helpers() -> None:
    with ScratchFile() as sf:
        # Both methods are intentional no-ops for parity-named call sites.
        assert sf.init_pages() is None
        assert sf.enlarge() is None
        # State is unchanged after the no-ops.
        assert sf.get_page_count() == 0

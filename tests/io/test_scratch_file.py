from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.io import (
    DEFAULT_PAGE_SIZE,
    NO_FREE_PAGE,
    MemoryUsageSetting,
    RandomAccessReadBuffer,
    ScratchFile,
    StorageMode,
)


def test_default_setting_is_main_memory_only() -> None:
    sf = ScratchFile()
    try:
        assert sf.setting.is_main_memory_only()
    finally:
        sf.close()


def test_main_memory_buffer_round_trip() -> None:
    with ScratchFile(MemoryUsageSetting.setup_main_memory_only()) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"hello, scratch")
        buf.seek(0)
        out = bytearray(14)
        assert buf.read_into(out) == 14
        assert bytes(out) == b"hello, scratch"
        assert buf.length() == 14


def test_temp_file_buffer_round_trip() -> None:
    with ScratchFile(MemoryUsageSetting.setup_temp_file_only()) as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"on disk")
        buf.seek(0)
        out = bytearray(7)
        assert buf.read_into(out) == 7
        assert bytes(out) == b"on disk"


def test_mixed_buffer_round_trip_below_threshold() -> None:
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=1024)
    with ScratchFile(setting) as sf:
        buf = sf.create_buffer()
        payload = b"x" * 100  # well below 1 KiB threshold
        buf.write_bytes(payload)
        buf.seek(0)
        out = bytearray(100)
        assert buf.read_into(out) == 100
        assert bytes(out) == payload


def test_mixed_buffer_spills_above_threshold() -> None:
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=64)
    with ScratchFile(setting) as sf:
        buf = sf.create_buffer()
        payload = b"y" * 500  # exceeds 64-byte spill threshold
        buf.write_bytes(payload)
        buf.seek(0)
        out = bytearray(500)
        assert buf.read_into(out) == 500
        assert bytes(out) == payload


def test_clear_truncates_buffer() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"discard me")
        buf.clear()
        assert buf.length() == 0
        buf.write_bytes(b"new")
        buf.seek(0)
        out = bytearray(3)
        assert buf.read_into(out) == 3
        assert bytes(out) == b"new"


def test_seek_position_and_length_track_correctly() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"0123456789")
        buf.seek(4)
        assert buf.get_position() == 4
        assert buf.length() == 10
        assert buf.read() == ord("4")


def test_create_buffer_from_input() -> None:
    src = RandomAccessReadBuffer(b"copy this content")
    with ScratchFile() as sf:
        buf = sf.create_buffer_from_input(src)
        assert buf.length() == 17
        out = bytearray(17)
        assert buf.read_into(out) == 17
        assert bytes(out) == b"copy this content"


def test_close_scratchfile_closes_all_buffers() -> None:
    sf = ScratchFile()
    a = sf.create_buffer()
    b = sf.create_buffer()
    sf.close()
    assert sf.is_closed()
    assert a.is_closed()
    assert b.is_closed()


def test_create_buffer_after_close_raises() -> None:
    sf = ScratchFile()
    sf.close()
    # Upstream ScratchFile#checkClosed → IOException("Scratch file already
    # closed") → OSError in pypdfbox (oracle-confirmed, wave 1483).
    with pytest.raises(OSError, match="Scratch file already closed"):
        sf.create_buffer()


def test_buffer_close_removes_from_owner_set() -> None:
    sf = ScratchFile()
    buf = sf.create_buffer()
    buf.close()
    assert buf.is_closed()
    sf.close()  # should not error trying to re-close


def test_invalid_byte_value_raises() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        with pytest.raises(ValueError):
            buf.write(-1)
        with pytest.raises(ValueError):
            buf.write(256)


# ---------------------------------------------------------------------------
# Page-oriented API (upstream parity).
# ---------------------------------------------------------------------------


def test_default_page_size_is_4kib() -> None:
    assert DEFAULT_PAGE_SIZE == 4096
    with ScratchFile() as sf:
        assert sf.get_page_size() == 4096
        assert sf.page_size == 4096


def test_custom_page_size_is_honoured() -> None:
    with ScratchFile(page_size=64) as sf:
        assert sf.get_page_size() == 64


def test_invalid_page_size_rejected() -> None:
    with pytest.raises(ValueError):
        ScratchFile(page_size=0)
    with pytest.raises(ValueError):
        ScratchFile(page_size=-128)


def test_get_new_page_returns_sequential_indices() -> None:
    with ScratchFile(page_size=32) as sf:
        a = sf.get_new_page()
        b = sf.get_new_page()
        c = sf.get_new_page()
        assert (a, b, c) == (0, 1, 2)
        assert sf.get_page_count() == 3


def test_get_new_page_after_close_raises() -> None:
    sf = ScratchFile()
    sf.close()
    with pytest.raises(OSError, match="Scratch file already closed"):
        sf.get_new_page()


def test_write_and_read_full_page() -> None:
    with ScratchFile(page_size=32) as sf:
        idx = sf.get_new_page()
        payload = bytes(range(32))
        sf.write_page(idx, payload)
        out = bytearray(32)
        n = sf.read_page(idx, out)
        assert n == 32
        assert bytes(out) == payload


def test_write_partial_page_zero_pads() -> None:
    with ScratchFile(page_size=16) as sf:
        idx = sf.get_new_page()
        sf.write_page(idx, b"abc", length=3)
        out = bytearray(16)
        sf.read_page(idx, out)
        assert bytes(out[:3]) == b"abc"
        assert bytes(out[3:]) == bytes(13)


def test_write_with_offset_in_source_buffer() -> None:
    with ScratchFile(page_size=8) as sf:
        idx = sf.get_new_page()
        src = b"prefix-DATA0123"
        sf.write_page(idx, src, offset=7, length=8)
        out = bytearray(8)
        sf.read_page(idx, out, length=8)
        assert bytes(out) == b"DATA0123"


def test_read_with_offset_into_destination_buffer() -> None:
    with ScratchFile(page_size=4) as sf:
        idx = sf.get_new_page()
        sf.write_page(idx, b"WXYZ")
        dest = bytearray(b"....????....")
        sf.read_page(idx, dest, offset=4, length=4)
        assert bytes(dest) == b"....WXYZ...."


def test_read_page_unwritten_returns_zeros() -> None:
    with ScratchFile(page_size=8) as sf:
        idx = sf.get_new_page()
        out = bytearray(8)
        sf.read_page(idx, out)
        assert bytes(out) == bytes(8)


def test_invalid_page_index_raises_on_read_and_write() -> None:
    with ScratchFile(page_size=8) as sf:
        with pytest.raises(IndexError):
            sf.read_page(0, bytearray(8))
        with pytest.raises(IndexError):
            sf.write_page(7, b"x" * 8)


def test_length_exceeding_page_size_raises() -> None:
    with ScratchFile(page_size=8) as sf:
        idx = sf.get_new_page()
        with pytest.raises(ValueError):
            sf.write_page(idx, b"x" * 16, length=16)
        with pytest.raises(ValueError):
            sf.read_page(idx, bytearray(16), length=16)


def test_negative_length_raises() -> None:
    with ScratchFile(page_size=8) as sf:
        idx = sf.get_new_page()
        with pytest.raises(ValueError):
            sf.write_page(idx, b"abc", length=-1)


def test_mark_pages_as_free_then_get_new_page_reuses() -> None:
    with ScratchFile(page_size=8) as sf:
        i0 = sf.get_new_page()
        i1 = sf.get_new_page()
        sf.write_page(i0, b"keep0000")
        sf.write_page(i1, b"toss0000")
        sf.mark_pages_as_free([i1])
        # Reuse: next allocation hands back a previously freed slot.
        reused = sf.get_new_page()
        assert reused == i1
        # And content was zero'd, so nothing leaks.
        out = bytearray(8)
        sf.read_page(reused, out)
        assert bytes(out) == bytes(8)
        # Page count unchanged (no growth on reuse).
        assert sf.get_page_count() == 2


def test_mark_pages_as_free_ignores_invalid_indices() -> None:
    with ScratchFile(page_size=8) as sf:
        sf.get_new_page()
        # Out-of-range indices are silently ignored, not raised.
        sf.mark_pages_as_free([-1, 999, 0])
        # The legit free of page 0 should still drive reuse.
        assert sf.dequeue_page() == 0


def test_mark_pages_as_free_idempotent() -> None:
    with ScratchFile(page_size=8) as sf:
        idx = sf.get_new_page()
        sf.mark_pages_as_free([idx])
        sf.mark_pages_as_free([idx])  # second call is a no-op
        assert sf.dequeue_page() == idx
        assert sf.dequeue_page() == NO_FREE_PAGE


def test_dequeue_page_empty_returns_sentinel() -> None:
    with ScratchFile() as sf:
        assert sf.dequeue_page() == NO_FREE_PAGE


def test_enqueue_page_alias_for_mark_pages_as_free() -> None:
    with ScratchFile(page_size=8) as sf:
        idx = sf.get_new_page()
        sf.enqueue_page(idx)
        assert sf.dequeue_page() == idx


def test_get_main_memory_max_pages_reflects_setting() -> None:
    # Default (UNLIMITED) -> -1 sentinel.
    with ScratchFile() as sf:
        assert sf.get_main_memory_max_pages() == -1

    # Explicit cap -> cap // page_size.
    setting = MemoryUsageSetting.setup_main_memory_only(max_main_memory_bytes=4096)
    with ScratchFile(setting, page_size=512) as sf:
        assert sf.get_main_memory_max_pages() == 8

    # TEMP_FILE_ONLY -> 0 main-memory pages allowed.
    with ScratchFile(MemoryUsageSetting.setup_temp_file_only()) as sf:
        assert sf.get_main_memory_max_pages() == 0


def test_temp_file_only_pages_round_trip() -> None:
    with ScratchFile(MemoryUsageSetting.setup_temp_file_only(), page_size=64) as sf:
        idx = sf.get_new_page()
        payload = b"\xde\xad\xbe\xef" * 16  # exactly 64 bytes
        sf.write_page(idx, payload)
        out = bytearray(64)
        sf.read_page(idx, out)
        assert bytes(out) == payload


def test_temp_file_uses_configured_temp_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen_dirs: list[object] = []

    def fake_temporary_file(*, mode: str, dir: object | None = None) -> io.BytesIO:
        assert mode == "w+b"
        seen_dirs.append(dir)
        return io.BytesIO()

    setting = MemoryUsageSetting.setup_temp_file_only().set_temp_dir(tmp_path)
    monkeypatch.setattr("pypdfbox.io.scratch_file.tempfile.TemporaryFile", fake_temporary_file)

    with ScratchFile(setting):
        pass

    assert seen_dirs == [tmp_path]


def test_mixed_mode_spills_pages_above_cap() -> None:
    # Cap allows 2 pages in RAM at 16 bytes each.
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=32)
    with ScratchFile(setting, page_size=16) as sf:
        ids = [sf.get_new_page() for _ in range(5)]
        for i, idx in enumerate(ids):
            sf.write_page(idx, bytes([i]) * 16)
        for i, idx in enumerate(ids):
            out = bytearray(16)
            sf.read_page(idx, out)
            assert bytes(out) == bytes([i]) * 16


def test_setting_property_exposed() -> None:
    setting = MemoryUsageSetting.setup_main_memory_only()
    with ScratchFile(setting) as sf:
        assert sf.setting is setting
        assert sf.setting.mode is StorageMode.MAIN_MEMORY_ONLY


def test_get_main_memory_only_instance_factory_no_arg() -> None:
    sf = ScratchFile.get_main_memory_only_instance()
    try:
        assert sf.setting.is_main_memory_only()
    finally:
        sf.close()


def test_get_main_memory_only_instance_factory_with_explicit_cap() -> None:
    sf = ScratchFile.get_main_memory_only_instance(max_main_memory_bytes=8192)
    try:
        assert sf.setting.is_main_memory_only()
        assert sf.setting.max_main_memory_bytes == 8192
    finally:
        sf.close()


def test_close_releases_pages_and_buffers() -> None:
    sf = ScratchFile(page_size=8)
    sf.get_new_page()
    sf.create_buffer()
    sf.close()
    # All page-API operations must reject calls on a closed scratch file.
    # Upstream checkClosed() → IOException("Scratch file already closed") →
    # OSError in pypdfbox (wave 1483).
    with pytest.raises(OSError, match="Scratch file already closed"):
        sf.get_new_page()
    with pytest.raises(OSError, match="Scratch file already closed"):
        sf.read_page(0, bytearray(8))
    with pytest.raises(OSError, match="Scratch file already closed"):
        sf.write_page(0, b"x" * 8)
    with pytest.raises(OSError, match="Scratch file already closed"):
        sf.mark_pages_as_free([0])
    with pytest.raises(OSError, match="Scratch file already closed"):
        sf.dequeue_page()

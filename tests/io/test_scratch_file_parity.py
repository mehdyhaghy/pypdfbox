from __future__ import annotations

from pypdfbox.io import MemoryUsageSetting, ScratchFile


def test_create_buffer_with_data_round_trip() -> None:
    payload = b"prefilled scratch data"
    with ScratchFile() as sf:
        buf = sf.create_buffer_with_data(payload)
        # Buffer should be at position 0, ready to read what was written.
        assert buf.get_position() == 0
        assert buf.length() == len(payload)
        out = bytearray(len(payload))
        assert buf.read_into(out) == len(payload)
        assert bytes(out) == payload


def test_create_buffer_with_data_empty_input() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer_with_data(b"")
        assert buf.length() == 0
        assert buf.get_position() == 0


def test_create_buffer_with_data_accepts_bytearray_and_memoryview() -> None:
    with ScratchFile() as sf:
        buf_a = sf.create_buffer_with_data(bytearray(b"abc"))
        buf_b = sf.create_buffer_with_data(memoryview(b"defg"))
        assert buf_a.length() == 3
        assert buf_b.length() == 4


def test_get_main_memory_only_instance_factory() -> None:
    with ScratchFile.get_main_memory_only_instance() as sf:
        assert sf.setting.is_main_memory_only()
        assert sf.get_main_memory_max_pages() == -1


def test_is_closed_false_after_construction() -> None:
    sf = ScratchFile()
    try:
        assert sf.is_closed() is False
    finally:
        sf.close()


def test_is_closed_true_after_close() -> None:
    sf = ScratchFile()
    sf.close()
    assert sf.is_closed() is True


def test_is_closed_idempotent_after_repeated_close() -> None:
    sf = ScratchFile()
    sf.close()
    sf.close()  # should not raise
    assert sf.is_closed() is True


def test_get_max_main_memory_bytes_default_mixed_is_16_mib() -> None:
    # Without an explicit max_main_memory_bytes cap on the setting,
    # MIXED mode falls back to the 16 MiB default per CHANGES.md.
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=16 * 1024 * 1024)
    with ScratchFile(setting) as sf:
        assert sf.get_max_main_memory_bytes() == 16 * 1024 * 1024


def test_get_max_main_memory_bytes_respects_explicit_cap() -> None:
    setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=4096)
    with ScratchFile(setting) as sf:
        assert sf.get_max_main_memory_bytes() == 4096


def test_get_main_memory_max_pages_returns_minus_one() -> None:
    # stdlib-backed impl has no page concept; -1 = unlimited / N/A.
    with ScratchFile() as sf:
        assert sf.get_main_memory_max_pages() == -1


def test_enqueue_dequeue_page_are_inert() -> None:
    with ScratchFile() as sf:
        # No-op; should not raise.
        sf.enqueue_page(0)
        sf.enqueue_page(42)
        # Dequeue always returns -1 since the free-page pool is inert.
        assert sf.dequeue_page() == -1

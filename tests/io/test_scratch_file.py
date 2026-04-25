from __future__ import annotations

import pytest

from pypdfbox.io import (
    MemoryUsageSetting,
    RandomAccessReadBuffer,
    ScratchFile,
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
    with pytest.raises(ValueError):
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

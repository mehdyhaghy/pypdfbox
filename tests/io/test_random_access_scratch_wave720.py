from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io import RandomAccessReadMemoryMapped, ScratchFile
from pypdfbox.io import random_access_read_memory_mapped as mmap_mod


def test_wave720_scratch_file_buffer_context_manager_closes() -> None:
    with ScratchFile(page_size=8) as scratch:
        with scratch.create_buffer() as buffer:
            buffer.write_bytes(b"abc")
            assert buffer.length() == 3

        assert buffer.is_closed()


def test_wave720_scratch_file_buffer_zero_length_read_preserves_position() -> None:
    with ScratchFile(page_size=8) as scratch:
        buffer = scratch.create_buffer()
        buffer.write_bytes(b"abcdef")
        buffer.seek(2)
        out = bytearray(b"xxxx")

        assert buffer.read_into(out, 1, 0) == 0
        assert out == bytearray(b"xxxx")
        assert buffer.get_position() == 2


def test_wave720_scratch_file_buffer_validates_read_ranges() -> None:
    with ScratchFile(page_size=8) as scratch:
        buffer = scratch.create_buffer()
        buffer.write_bytes(b"abc")
        buffer.seek(0)

        with pytest.raises(ValueError, match="length must be non-negative"):
            buffer.read_into(bytearray(3), 0, -1)
        with pytest.raises(ValueError, match="offset/length out of range"):
            buffer.read_into(bytearray(3), 2, 2)


def test_wave720_scratch_file_buffer_validates_write_ranges() -> None:
    with ScratchFile(page_size=8) as scratch:
        buffer = scratch.create_buffer()

        with pytest.raises(ValueError, match="length must be non-negative"):
            buffer.write_bytes(b"abc", 0, -1)
        with pytest.raises(ValueError, match="offset/length out of range"):
            buffer.write_bytes(b"abc", 2, 2)


def test_wave720_scratch_file_buffer_internal_empty_read_returns_eof() -> None:
    with ScratchFile(page_size=8) as scratch:
        buffer = scratch.create_buffer()
        buffer.write_bytes(b"abc")
        buffer.seek(4)

        assert buffer._read_into_view(memoryview(bytearray(1)), 1) == buffer.EOF


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    path = tmp_path / "mapped.bin"
    path.write_bytes(b"abcdefghij")
    return path


def test_wave720_memory_mapped_path_property(sample_file: Path) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as reader:
        assert reader.path == sample_file


def test_wave720_memory_mapped_read_into_validates_ranges(sample_file: Path) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as reader:
        with pytest.raises(ValueError, match="length must be non-negative"):
            reader.read_into(bytearray(3), 0, -1)
        with pytest.raises(ValueError, match="offset/length out of range"):
            reader.read_into(bytearray(3), 2, 2)


def test_wave720_memory_mapped_zero_length_read_at_eof_returns_zero(
    sample_file: Path,
) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as reader:
        reader.seek(reader.length())

        assert reader.read_into(bytearray(3), 1, 0) == 0


def test_wave720_memory_mapped_close_is_idempotent(sample_file: Path) -> None:
    reader = RandomAccessReadMemoryMapped(sample_file)

    reader.close()
    reader.close()

    assert reader.is_closed()


def test_wave720_memory_mapped_closes_fd_when_mmap_constructor_fails(
    sample_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed_fds: list[int] = []
    real_close = mmap_mod.os.close

    def raising_mmap(*args: object, **kwargs: object) -> object:
        raise OSError("synthetic mmap failure")

    def spy_close(fd: int) -> None:
        closed_fds.append(fd)
        real_close(fd)

    monkeypatch.setattr(mmap_mod.mmap, "mmap", raising_mmap)
    monkeypatch.setattr(mmap_mod.os, "close", spy_close)

    with pytest.raises(OSError, match="synthetic mmap failure"):
        RandomAccessReadMemoryMapped(sample_file)

    assert len(closed_fds) == 1

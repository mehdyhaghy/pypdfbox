from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.io import (
    RandomAccessReadBuffer,
    RandomAccessReadBufferedFile,
    RandomAccessReadMemoryMapped,
    RandomAccessReadView,
    RandomAccessWriteBuffer,
    ScratchFile,
)


@pytest.mark.parametrize(
    "reader",
    [
        RandomAccessReadBuffer(b"abc"),
        RandomAccessReadView(RandomAccessReadBuffer(b"abc"), 0, 3),
    ],
)
def test_available_is_never_negative_after_seek_past_logical_end(
    reader: RandomAccessReadBuffer | RandomAccessReadView,
) -> None:
    reader.seek(99)

    assert reader.available() == 0
    assert reader.is_eof()


def test_scratch_file_buffer_available_is_never_negative_after_sparse_seek() -> None:
    with ScratchFile(page_size=8) as scratch:
        buf = scratch.create_buffer()
        buf.write_bytes(b"abc")
        buf.seek(99)

        assert buf.available() == 0
        assert buf.is_eof()


@pytest.mark.parametrize("data", [b"", b"abc"])
def test_zero_length_reads_at_eof_return_zero_for_read_wrappers(
    tmp_path: Path, data: bytes
) -> None:
    file_path = tmp_path / f"payload-{len(data)}.bin"
    file_path.write_bytes(data)

    readers = [
        RandomAccessReadBuffer(data),
        RandomAccessReadBufferedFile(file_path),
        RandomAccessReadMemoryMapped(file_path),
        RandomAccessReadView(RandomAccessReadBuffer(data), len(data), 3),
    ]
    try:
        for reader in readers:
            reader.seek(reader.length())
            assert reader.read_into(bytearray(), 0, 0) == 0
    finally:
        for reader in readers:
            reader.close()


def test_stream_source_must_yield_bytes() -> None:
    with pytest.raises(TypeError, match="source stream must yield bytes"):
        RandomAccessReadBuffer(io.StringIO("not-bytes"))  # type: ignore[arg-type]


def test_write_buffer_zero_length_slice_is_noop() -> None:
    writer = RandomAccessWriteBuffer()
    writer.write_bytes(b"prefix")
    writer.write_bytes(b"ignored", offset=3, length=0)

    assert writer.to_bytes() == b"prefix"
    assert writer.tell() == 6


def test_scratch_file_buffer_is_empty_tracks_clear() -> None:
    with ScratchFile(page_size=8) as scratch:
        buf = scratch.create_buffer()
        assert buf.is_empty()

        buf.write_bytes(b"x")
        assert not buf.is_empty()

        buf.clear()
        assert buf.is_empty()

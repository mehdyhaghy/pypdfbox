from __future__ import annotations

import io

import pytest

from pypdfbox.io import RandomAccessReadBuffer


class _ShortReadStream(io.BytesIO):
    def read(self, size: int | None = -1, /) -> bytes:
        chunk_size = 2 if size is None or size < 0 else min(size, 2)
        return super().read(chunk_size)


class _FailingAfterFirstChunkStream(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self._reads = 0

    def read(self, size: int | None = -1, /) -> bytes:
        self._reads += 1
        if self._reads > 1:
            raise RuntimeError("boom")
        chunk_size = 2 if size is None or size < 0 else min(size, 2)
        return super().read(chunk_size)


def test_random_access_read_buffer_wave329_reads_all_short_stream_chunks() -> None:
    reader = RandomAccessReadBuffer(_ShortReadStream(b"abcdef"))

    assert reader.length() == 6
    out = bytearray(6)
    assert reader.read_into(out) == 6
    assert bytes(out) == b"abcdef"


def test_create_buffer_from_stream_wave329_closes_after_late_read_failure() -> None:
    stream = _FailingAfterFirstChunkStream(b"abcd")

    with pytest.raises(RuntimeError, match="boom"):
        RandomAccessReadBuffer.create_buffer_from_stream(stream)

    assert stream.closed

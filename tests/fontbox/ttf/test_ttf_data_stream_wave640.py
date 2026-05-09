from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.fontbox.ttf.ttf_data_stream import (
    MemoryTTFDataStream,
    RandomAccessReadDataStream,
)
from pypdfbox.io import RandomAccessReadBuffer


def _memory(data: bytes) -> MemoryTTFDataStream:
    return MemoryTTFDataStream(data)


def _random_access(data: bytes) -> RandomAccessReadDataStream:
    return RandomAccessReadDataStream(RandomAccessReadBuffer(data))


@pytest.mark.parametrize("factory", [_memory, _random_access])
def test_read_into_rejects_too_large_length_before_partial_read(
    factory: Callable[[bytes], MemoryTTFDataStream | RandomAccessReadDataStream],
) -> None:
    stream = factory(b"xyz")
    buf = bytearray(b"..")

    with pytest.raises(IndexError, match="out of bounds"):
        stream.read_into(buf, 1, 2)

    assert bytes(buf) == b".."
    assert stream.get_current_position() == 0


@pytest.mark.parametrize("factory", [_memory, _random_access])
def test_read_into_accepts_exact_remaining_buffer_capacity(
    factory: Callable[[bytes], MemoryTTFDataStream | RandomAccessReadDataStream],
) -> None:
    stream = factory(b"xyz")
    buf = bytearray(b"..")

    assert stream.read_into(buf, 1, 1) == 1

    assert bytes(buf) == b".x"
    assert stream.get_current_position() == 1


@pytest.mark.parametrize("factory", [_memory, _random_access])
def test_read_into_rejects_negative_length_without_advancing(
    factory: Callable[[bytes], MemoryTTFDataStream | RandomAccessReadDataStream],
) -> None:
    stream = factory(b"abc")
    buf = bytearray(3)

    with pytest.raises(IndexError, match="out of bounds"):
        stream.read_into(buf, 0, -1)

    assert stream.get_current_position() == 0


@pytest.mark.parametrize("factory", [_memory, _random_access])
def test_read_into_allows_zero_length_at_end_of_buffer(
    factory: Callable[[bytes], MemoryTTFDataStream | RandomAccessReadDataStream],
) -> None:
    stream = factory(b"abc")
    buf = bytearray(b"12")

    assert stream.read_into(buf, len(buf), 0) == 0

    assert bytes(buf) == b"12"
    assert stream.get_current_position() == 0

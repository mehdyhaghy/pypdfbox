from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer


class _MemoryViewStream:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> memoryview:
        return memoryview(self._data)


class _NonCallableRead:
    read = b"not-callable"


def test_stream_source_may_return_memoryview() -> None:
    reader = RandomAccessReadBuffer(_MemoryViewStream(b"abc"))  # type: ignore[arg-type]

    assert reader.length() == 3
    assert reader.read() == ord("a")


def test_stream_source_read_attribute_must_be_callable() -> None:
    with pytest.raises(TypeError, match="source read attribute must be callable"):
        RandomAccessReadBuffer(_NonCallableRead())  # type: ignore[arg-type]

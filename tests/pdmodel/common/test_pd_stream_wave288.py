from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.common import PDStream


class _NonCallableRead:
    read = b"not callable"


class _TextRead(io.StringIO):
    pass


def test_pd_stream_rejects_source_with_non_callable_read_wave288() -> None:
    with pytest.raises(TypeError, match="callable read"):
        PDStream(None, _NonCallableRead())  # type: ignore[arg-type]


def test_pd_stream_rejects_text_returning_source_wave288() -> None:
    source = _TextRead("not bytes")

    with pytest.raises(TypeError, match="bytes-like data"):
        PDStream(None, source)  # type: ignore[arg-type]

    assert source.closed


def test_pd_stream_accepts_memoryview_returning_source_wave288() -> None:
    class MemoryViewRead:
        def __init__(self) -> None:
            self.closed = False

        def read(self) -> memoryview:
            return memoryview(b"payload")

        def close(self) -> None:
            self.closed = True

    source = MemoryViewRead()
    stream = PDStream(None, source)  # type: ignore[arg-type]

    assert source.closed is True
    assert stream.create_raw_input_stream().read() == b"payload"

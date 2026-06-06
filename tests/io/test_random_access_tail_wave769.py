from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io import (
    RandomAccessReadBuffer,
    RandomAccessReadBufferedFile,
    RandomAccessReadView,
)


class _NoArgReadStream:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def read(self, *args: object) -> object:
        if args:
            raise TypeError("read takes no size")
        return self.payload


def test_read_fully_rejects_negative_integer_length() -> None:
    reader = RandomAccessReadBuffer(b"abc")

    with pytest.raises(ValueError, match="non-negative"):
        reader.read_fully(-1)


def test_read_fully_rejects_invalid_bytearray_ranges() -> None:
    reader = RandomAccessReadBuffer(b"abc")
    buf = bytearray(3)

    with pytest.raises(ValueError, match="non-negative"):
        reader.read_fully(buf, length=-1)
    with pytest.raises(ValueError, match="out of range"):
        reader.read_fully(buf, offset=2, length=2)


def test_skip_negative_count_seeks_backward() -> None:
    # Upstream RandomAccessRead.skip(int) is seek(getPosition() + n) with no
    # sign check, so a negative n seeks backward (pinned wave 1496 against the
    # PDFBox 3.0.7 oracle). It does NOT raise.
    reader = RandomAccessReadBuffer(b"abc")
    reader.seek(2)
    reader.skip(-1)
    assert reader.get_position() == 1


def test_no_arg_empty_stream_constructor_path_builds_empty_buffer() -> None:
    reader = RandomAccessReadBuffer(_NoArgReadStream(b""))  # type: ignore[arg-type]

    assert reader.length() == 0
    assert reader.read() == -1


def test_no_arg_stream_constructor_rejects_non_bytes_payload() -> None:
    with pytest.raises(TypeError, match="yield bytes"):
        RandomAccessReadBuffer(_NoArgReadStream("not bytes"))  # type: ignore[arg-type]


def test_buffered_file_read_into_rejects_invalid_ranges(tmp_path: Path) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"abc")
    reader = RandomAccessReadBufferedFile(path)
    buf = bytearray(3)
    try:
        with pytest.raises(ValueError, match="non-negative"):
            reader.read_into(buf, length=-1)
        with pytest.raises(ValueError, match="out of range"):
            reader.read_into(buf, offset=2, length=2)
    finally:
        reader.close()


def test_view_read_into_rejects_invalid_ranges() -> None:
    parent = RandomAccessReadBuffer(b"abcdef")
    view = RandomAccessReadView(parent, 1, 3)
    buf = bytearray(3)

    with pytest.raises(ValueError, match="non-negative"):
        view.read_into(buf, length=-1)
    with pytest.raises(ValueError, match="out of range"):
        view.read_into(buf, offset=2, length=2)

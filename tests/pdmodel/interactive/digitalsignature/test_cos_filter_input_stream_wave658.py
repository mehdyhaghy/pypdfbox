from __future__ import annotations

from io import BytesIO

from pypdfbox.pdmodel.interactive.digitalsignature.cos_filter_input_stream import (
    COSFilterInputStream,
)


def test_overlapping_range_fully_behind_current_position_is_dropped() -> None:
    stream = COSFilterInputStream(bytes(range(20)), [0, 10, 5, 5])

    assert stream.read_all() == bytes(range(10))


def test_overlapping_range_partly_ahead_reads_only_remaining_tail() -> None:
    stream = COSFilterInputStream(bytes(range(20)), [0, 10, 5, 10])

    assert stream.read_all() == bytes(range(15))


def test_skip_source_ignores_non_positive_skip() -> None:
    stream = COSFilterInputStream(b"abc", [])

    stream._skip_source(0)

    assert stream.read_all() == b""


def test_seek_failure_falls_back_to_read_and_discard() -> None:
    class SeekFails:
        def __init__(self, data: bytes) -> None:
            self._buf = BytesIO(data)

        def read(self, size: int = -1) -> bytes:
            return self._buf.read(size)

        def seek(self, offset: int, whence: int = 0) -> int:
            raise OSError("seek unavailable")

        def tell(self) -> int:
            return self._buf.tell()

        def close(self) -> None:
            self._buf.close()

    stream = COSFilterInputStream(SeekFails(b"abcdef"), [2, 3])

    assert stream.read_all() == b"cde"
    assert stream._source.tell() == 5
    stream.close()


def test_skip_source_stops_when_source_ends_before_range_start() -> None:
    stream = COSFilterInputStream(b"abc", [10, 2])

    assert stream.read_all() == b""


def test_read_stops_when_source_is_empty_inside_active_range() -> None:
    stream = COSFilterInputStream(b"", [0, 5])

    assert stream.read(5) == b""


def test_close_is_idempotent() -> None:
    stream = COSFilterInputStream(b"abc", [0, 1])

    stream.close()
    stream.close()

    assert not stream.readable()

from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.io import (
    close_and_log_exception,
    close_quietly,
    copy,
    populate_buffer,
    to_byte_array,
    unmap,
)


def test_copy_returns_total_bytes_and_writes_all() -> None:
    src = io.BytesIO(b"the quick brown fox")
    dst = io.BytesIO()
    n = copy(src, dst)
    assert n == 19
    assert dst.getvalue() == b"the quick brown fox"


def test_copy_with_small_buffer_handles_multiple_reads() -> None:
    src = io.BytesIO(b"abcdefghij")
    dst = io.BytesIO()
    n = copy(src, dst, buffer_size=3)
    assert n == 10
    assert dst.getvalue() == b"abcdefghij"


def test_copy_invalid_buffer_size_raises() -> None:
    with pytest.raises(ValueError):
        copy(io.BytesIO(b""), io.BytesIO(), buffer_size=0)


def test_to_byte_array_reads_all() -> None:
    src = io.BytesIO(b"\x00\x01\x02\xff")
    assert to_byte_array(src) == b"\x00\x01\x02\xff"


def test_to_byte_array_empty() -> None:
    assert to_byte_array(io.BytesIO(b"")) == b""


def test_close_quietly_closes() -> None:
    src = io.BytesIO(b"abc")
    close_quietly(src)
    assert src.closed


def test_close_quietly_none_is_noop() -> None:
    close_quietly(None)


def test_close_quietly_swallows_exceptions() -> None:
    class Bad:
        def close(self) -> None:
            raise RuntimeError("boom")

    close_quietly(Bad())  # must not raise


def test_populate_buffer_fills_completely() -> None:
    src = io.BytesIO(b"abcdef")
    buf = bytearray(6)
    n = populate_buffer(src, buf)
    assert n == 6
    assert bytes(buf) == b"abcdef"


def test_populate_buffer_partial_at_eof() -> None:
    src = io.BytesIO(b"abc")
    buf = bytearray(10)
    n = populate_buffer(src, buf)
    assert n == 3
    assert bytes(buf[:3]) == b"abc"


def test_populate_buffer_handles_short_reads() -> None:
    """A stream that returns small chunks should still completely fill the buffer."""

    class Drip(io.BytesIO):
        def read(self, size: int = -1) -> bytes:  # type: ignore[override]
            return super().read(min(size, 1) if size > 0 else size)

    src = Drip(b"abcdef")
    buf = bytearray(6)
    n = populate_buffer(src, buf)
    assert n == 6
    assert bytes(buf) == b"abcdef"


# ----- close_and_log_exception parity -----


def test_close_and_log_exception_success_returns_initial_none() -> None:
    src = io.BytesIO(b"hi")
    result = close_and_log_exception(
        src, logging.getLogger("pypdfbox.tests.iou"), "src"
    )
    assert result is None
    assert src.closed


def test_close_and_log_exception_success_returns_initial_when_set() -> None:
    src = io.BytesIO(b"hi")
    initial = OSError("earlier failure")
    result = close_and_log_exception(
        src, logging.getLogger("pypdfbox.tests.iou"), "src", initial
    )
    assert result is initial
    assert src.closed


def test_close_and_log_exception_returns_close_error_when_initial_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class Bad:
        def close(self) -> None:
            raise OSError("close kaboom")

    logger = logging.getLogger("pypdfbox.tests.iou.bad")
    caplog.set_level(logging.WARNING, logger="pypdfbox.tests.iou.bad")
    result = close_and_log_exception(Bad(), logger, "the-resource")
    assert isinstance(result, OSError)
    assert "close kaboom" in str(result)
    assert any("the-resource" in r.getMessage() for r in caplog.records)


def test_close_and_log_exception_preserves_initial_on_close_failure() -> None:
    class Bad:
        def close(self) -> None:
            raise OSError("close kaboom")

    initial = RuntimeError("primary problem")
    logger = logging.getLogger("pypdfbox.tests.iou.bad2")
    result = close_and_log_exception(Bad(), logger, "res", initial)
    # Initial exception is returned unchanged so the caller doesn't lose it.
    assert result is initial


# ----- unmap stub -----


def test_unmap_none_is_noop() -> None:
    unmap(None)  # must not raise


def test_unmap_calls_close_on_object_with_close() -> None:
    closed = []

    class FakeMmap:
        def close(self) -> None:
            closed.append(True)

    unmap(FakeMmap())
    assert closed == [True]


def test_unmap_swallows_close_errors() -> None:
    class Bad:
        def close(self) -> None:
            raise RuntimeError("nope")

    unmap(Bad())  # must not raise


def test_unmap_object_without_close_is_noop() -> None:
    unmap(b"\x00\x01\x02")  # bytes have no close — must not raise

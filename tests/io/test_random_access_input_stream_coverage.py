"""Wave 1321: RandomAccessInputStream coverage-boost tests.

Covers the proxy plumbing (``readable``, ``read1``, ``seekable``,
``read(0)``), the ``readinto`` memoryview branch, and the defensive
exception/EOF paths in ``available`` and ``_read_into`` using small
stub :class:`RandomAccessRead` implementations.
"""

from __future__ import annotations

from pypdfbox.io import RandomAccessInputStream, RandomAccessReadBuffer
from pypdfbox.io.random_access_read import RandomAccessRead


def test_readable_returns_true() -> None:
    stream = RandomAccessInputStream(RandomAccessReadBuffer(b""))
    assert stream.readable() is True


def test_seekable_returns_false() -> None:
    # The adapter does not expose seek; mirrors upstream's
    # ``InputStream`` contract.
    stream = RandomAccessInputStream(RandomAccessReadBuffer(b"abc"))
    assert stream.seekable() is False


def test_read_zero_returns_empty() -> None:
    stream = RandomAccessInputStream(RandomAccessReadBuffer(b"abc"))
    assert stream.read(0) == b""
    # Position is untouched.
    assert stream.tell() == 0


def test_read1_delegates_to_read() -> None:
    stream = RandomAccessInputStream(RandomAccessReadBuffer(b"hello"))
    assert stream.read1(3) == b"hel"
    assert stream.tell() == 3


def test_readinto_with_memoryview_copies_data() -> None:
    stream = RandomAccessInputStream(RandomAccessReadBuffer(b"abcdef"))
    underlying = bytearray(4)
    view = memoryview(underlying)
    n = stream.readinto(view)
    assert n == 4
    assert bytes(underlying) == b"abcd"


def test_readinto_with_memoryview_at_eof_returns_zero() -> None:
    stream = RandomAccessInputStream(RandomAccessReadBuffer(b""))
    underlying = bytearray(4)
    n = stream.readinto(memoryview(underlying))
    assert n == 0


def test_readinto_with_bytearray_takes_fast_path() -> None:
    # bytearray (not memoryview) goes through the second branch
    # (line 90) — direct delegation without an intermediate copy.
    stream = RandomAccessInputStream(RandomAccessReadBuffer(b"xyzw"))
    out = bytearray(4)
    n = stream.readinto(out)
    assert n == 4
    assert bytes(out) == b"xyzw"


def test_available_returns_zero_when_length_raises() -> None:
    class _BrokenLen(RandomAccessRead):
        def read(self) -> int:
            return self.EOF

        def read_into(
            self,
            buf: bytearray,
            offset: int = 0,
            length: int | None = None,
        ) -> int:
            return self.EOF

        def get_position(self) -> int:
            return 0

        def seek(self, position: int) -> None:
            return None

        def length(self) -> int:
            raise RuntimeError("no length")

        def close(self) -> None:
            return None

        def is_closed(self) -> bool:
            return False

    stream = RandomAccessInputStream(_BrokenLen())
    # ``available`` swallows the exception and returns 0.
    assert stream.available() == 0


def test_read_into_handles_is_eof_exception() -> None:
    class _BrokenEof(RandomAccessRead):
        def read(self) -> int:
            return self.EOF

        def read_into(
            self,
            buf: bytearray,
            offset: int = 0,
            length: int | None = None,
        ) -> int:
            return self.EOF

        def get_position(self) -> int:
            return 0

        def seek(self, position: int) -> None:
            return None

        def length(self) -> int:
            return 0

        def close(self) -> None:
            return None

        def is_closed(self) -> bool:
            return False

        def is_eof(self) -> bool:
            raise RuntimeError("boom")

    stream = RandomAccessInputStream(_BrokenEof())
    # ``_read_into`` returns -1 → ``read`` yields empty bytes.
    assert stream.read(4) == b""


def test_read_into_logs_when_inner_returns_minus_one(
    caplog: object,
) -> None:
    # Stub that reports not-EOF but whose ``read_into`` returns -1 —
    # exercises the warning branch (line 103).
    class _LiarStream(RandomAccessRead):
        def __init__(self) -> None:
            self._pos = 0

        def read(self) -> int:
            return self.EOF

        def read_into(
            self,
            buf: bytearray,
            offset: int = 0,
            length: int | None = None,
        ) -> int:
            return -1

        def get_position(self) -> int:
            return self._pos

        def seek(self, position: int) -> None:
            self._pos = position

        def length(self) -> int:
            return 100

        def close(self) -> None:
            return None

        def is_closed(self) -> bool:
            return False

        def is_eof(self) -> bool:
            # Pretend bytes remain so ``_read_into`` falls through to
            # ``read_into`` and hits the logging branch.
            return False

    import logging

    import pytest  # noqa: PLC0415

    caplog_fix: pytest.LogCaptureFixture = caplog  # type: ignore[assignment]
    with caplog_fix.at_level(
        logging.ERROR,
        logger="pypdfbox.io.random_access_input_stream",
    ):
        stream = RandomAccessInputStream(_LiarStream())
        assert stream.read(8) == b""
    assert any("read() returns -1" in rec.message for rec in caplog_fix.records)

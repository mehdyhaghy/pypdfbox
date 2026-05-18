"""Tests for ``pypdfbox.benchmark.null_output_stream``."""
from __future__ import annotations

from pypdfbox.benchmark.null_output_stream import NullOutputStream


def test_write_returns_length() -> None:
    stream = NullOutputStream()
    assert stream.write(b"hello") == 5
    assert stream.write(b"") == 0


def test_write_accepts_bytearray() -> None:
    stream = NullOutputStream()
    assert stream.write(bytearray(b"world")) == 5


def test_write_accepts_memoryview() -> None:
    stream = NullOutputStream()
    assert stream.write(memoryview(b"abc")) == 3


def test_writable_is_true() -> None:
    stream = NullOutputStream()
    assert stream.writable() is True


def test_flush_does_not_raise() -> None:
    stream = NullOutputStream()
    stream.flush()


def test_write_none_returns_zero() -> None:
    """Mirror upstream's ``write(byte[] b)`` no-op for ``null`` —
    the Python port returns 0 instead of raising NPE."""
    stream = NullOutputStream()
    assert stream.write(None) == 0  # type: ignore[arg-type]

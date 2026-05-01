from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessWriteBuffer


def test_single_byte_writes_accumulate() -> None:
    w = RandomAccessWriteBuffer()
    w.write(0x41)
    w.write(0x42)
    w.write(0x43)
    assert w.to_bytes() == b"ABC"
    assert w.length() == 3


def test_byte_value_out_of_range_raises() -> None:
    w = RandomAccessWriteBuffer()
    with pytest.raises(ValueError):
        w.write(-1)
    with pytest.raises(ValueError):
        w.write(256)


def test_write_bytes_appends() -> None:
    w = RandomAccessWriteBuffer()
    w.write_bytes(b"hello")
    w.write_bytes(b", world")
    assert w.to_bytes() == b"hello, world"


def test_write_bytes_with_offset_and_length() -> None:
    w = RandomAccessWriteBuffer()
    w.write_bytes(b"0123456789", offset=2, length=4)
    assert w.to_bytes() == b"2345"


def test_write_bytes_invalid_args_raise() -> None:
    w = RandomAccessWriteBuffer()
    with pytest.raises(ValueError):
        w.write_bytes(b"abc", offset=-1)
    with pytest.raises(ValueError):
        w.write_bytes(b"abc", offset=0, length=-1)
    with pytest.raises(ValueError):
        w.write_bytes(b"abc", offset=2, length=10)


def test_clear_resets_buffer() -> None:
    w = RandomAccessWriteBuffer()
    w.write_bytes(b"keep me")
    w.clear()
    assert w.to_bytes() == b""
    assert w.length() == 0
    w.write_bytes(b"after")
    assert w.to_bytes() == b"after"


def test_close_makes_operations_raise() -> None:
    w = RandomAccessWriteBuffer()
    w.close()
    assert w.is_closed()
    with pytest.raises(ValueError):
        w.write(0x41)
    with pytest.raises(ValueError):
        w.write_bytes(b"x")


def test_close_is_idempotent() -> None:
    w = RandomAccessWriteBuffer()
    w.close()
    w.close()
    assert w.is_closed()


def test_context_manager() -> None:
    with RandomAccessWriteBuffer() as w:
        w.write_bytes(b"ctx")
        assert w.to_bytes() == b"ctx"
    assert w.is_closed()


def test_is_closed_camelcase_alias() -> None:
    w = RandomAccessWriteBuffer()
    assert not w.isClosed()
    w.close()
    assert w.isClosed()

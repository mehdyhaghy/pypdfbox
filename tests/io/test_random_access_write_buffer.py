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
    # Upstream parity: RandomAccessReadWriteBuffer inherits checkClosed() from
    # RandomAccessReadBuffer → IOException("RandomAccessBuffer already closed");
    # mapped to OSError with the exact message (oracle-confirmed, wave 1483).
    with pytest.raises(OSError, match="RandomAccessBuffer already closed"):
        w.write(0x41)
    with pytest.raises(OSError, match="RandomAccessBuffer already closed"):
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


def test_is_empty_initial_and_after_writes() -> None:
    w = RandomAccessWriteBuffer()
    assert w.is_empty()
    w.write_bytes(b"x")
    assert not w.is_empty()


def test_is_empty_after_clear() -> None:
    w = RandomAccessWriteBuffer()
    w.write_bytes(b"discard")
    assert not w.is_empty()
    w.clear()
    assert w.is_empty()


def test_is_empty_raises_when_closed() -> None:
    w = RandomAccessWriteBuffer()
    w.close()
    with pytest.raises(OSError, match="RandomAccessBuffer already closed"):
        w.is_empty()


def test_dunder_len_matches_length() -> None:
    w = RandomAccessWriteBuffer()
    assert len(w) == 0
    w.write_bytes(b"abcde")
    assert len(w) == 5
    assert len(w) == w.length()


def test_dunder_bytes_matches_to_bytes() -> None:
    w = RandomAccessWriteBuffer()
    w.write_bytes(b"hello")
    assert bytes(w) == b"hello"
    assert bytes(w) == w.to_bytes()


def test_dunder_bytes_empty() -> None:
    w = RandomAccessWriteBuffer()
    assert bytes(w) == b""


def test_tell_advances_with_writes() -> None:
    w = RandomAccessWriteBuffer()
    assert w.tell() == 0
    w.write(0x41)
    assert w.tell() == 1
    w.write_bytes(b"BCD")
    assert w.tell() == 4


def test_tell_resets_with_clear() -> None:
    w = RandomAccessWriteBuffer()
    w.write_bytes(b"abcdef")
    assert w.tell() == 6
    w.clear()
    assert w.tell() == 0


def test_tell_raises_when_closed() -> None:
    w = RandomAccessWriteBuffer()
    w.close()
    with pytest.raises(OSError, match="RandomAccessBuffer already closed"):
        w.tell()

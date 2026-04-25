from __future__ import annotations

import io

import pytest

from pypdfbox.io import RandomAccessReadBuffer


def test_construction_from_bytes_records_length() -> None:
    rab = RandomAccessReadBuffer(b"hello, world")
    assert rab.length() == 12
    assert rab.get_position() == 0
    assert not rab.is_closed()


def test_construction_from_stream_consumes_to_eof() -> None:
    stream = io.BytesIO(b"abcdefghij")
    rab = RandomAccessReadBuffer(stream)
    assert rab.length() == 10
    assert rab.get_position() == 0


def test_sequential_single_byte_read() -> None:
    rab = RandomAccessReadBuffer(b"AB")
    assert rab.read() == ord("A")
    assert rab.read() == ord("B")
    assert rab.read() == -1  # EOF
    assert rab.is_eof()


def test_read_into_partial_then_eof() -> None:
    rab = RandomAccessReadBuffer(b"abcdef")
    buf = bytearray(4)
    n = rab.read_into(buf)
    assert n == 4
    assert bytes(buf) == b"abcd"
    n = rab.read_into(buf)
    assert n == 2
    assert bytes(buf[:2]) == b"ef"
    n = rab.read_into(buf)
    assert n == -1  # subsequent read at EOF


def test_read_into_with_offset_and_length() -> None:
    rab = RandomAccessReadBuffer(b"0123456789")
    buf = bytearray(b"....##....")
    n = rab.read_into(buf, offset=4, length=2)
    assert n == 2
    assert bytes(buf) == b"....01...."
    assert rab.get_position() == 2


def test_seek_and_position() -> None:
    rab = RandomAccessReadBuffer(b"abcdefghij")
    rab.seek(5)
    assert rab.get_position() == 5
    assert rab.read() == ord("f")


def test_seek_negative_raises() -> None:
    rab = RandomAccessReadBuffer(b"abc")
    with pytest.raises(OSError):
        rab.seek(-1)


def test_seek_past_end_clamps_to_eof() -> None:
    # PDFBox semantics: seeking past length is allowed; position clamps to length.
    rab = RandomAccessReadBuffer(b"abc")
    rab.seek(100)
    assert rab.is_eof()
    assert rab.get_position() == 3


def test_peek_does_not_advance_position() -> None:
    rab = RandomAccessReadBuffer(b"xy")
    assert rab.peek() == ord("x")
    assert rab.get_position() == 0
    assert rab.read() == ord("x")


def test_peek_at_eof_returns_minus_one() -> None:
    rab = RandomAccessReadBuffer(b"")
    assert rab.peek() == -1


def test_rewind_moves_position_back() -> None:
    rab = RandomAccessReadBuffer(b"hello")
    rab.read()
    rab.read()
    rab.rewind(2)
    assert rab.get_position() == 0


def test_rewind_negative_raises() -> None:
    rab = RandomAccessReadBuffer(b"x")
    with pytest.raises(ValueError):
        rab.rewind(-1)


def test_unread_int_and_bytes() -> None:
    rab = RandomAccessReadBuffer(b"abcdef")
    rab.read()
    rab.read()
    rab.unread(b"ab")
    assert rab.get_position() == 0
    rab.read()
    rab.unread(0x41)  # int form rewinds 1
    assert rab.get_position() == 0


def test_available_and_is_eof() -> None:
    rab = RandomAccessReadBuffer(b"abc")
    assert rab.available() == 3
    rab.read()
    assert rab.available() == 2
    rab.seek(3)
    assert rab.is_eof()
    assert rab.available() == 0


def test_large_payload_round_trips_correctly() -> None:
    payload = bytes(range(256)) * 1000  # 256,000 bytes
    rab = RandomAccessReadBuffer(payload)
    out = bytearray(len(payload))
    n = rab.read_into(out)
    assert n == len(payload)
    assert bytes(out) == payload


def test_close_makes_operations_raise() -> None:
    rab = RandomAccessReadBuffer(b"abc")
    rab.close()
    assert rab.is_closed()
    with pytest.raises(ValueError):
        rab.read()
    with pytest.raises(ValueError):
        rab.length()


def test_close_is_idempotent() -> None:
    rab = RandomAccessReadBuffer(b"abc")
    rab.close()
    rab.close()
    assert rab.is_closed()


def test_context_manager_closes_on_exit() -> None:
    with RandomAccessReadBuffer(b"abc") as rab:
        assert rab.read() == ord("a")
    assert rab.is_closed()


def test_invalid_source_type_raises() -> None:
    with pytest.raises(TypeError):
        RandomAccessReadBuffer(123)  # type: ignore[arg-type]


def test_read_into_invalid_offset_or_length_raises() -> None:
    rab = RandomAccessReadBuffer(b"abc")
    buf = bytearray(4)
    with pytest.raises(ValueError):
        rab.read_into(buf, offset=-1)
    with pytest.raises(ValueError):
        rab.read_into(buf, offset=0, length=-1)
    with pytest.raises(ValueError):
        rab.read_into(buf, offset=2, length=10)


def test_factory_constructors() -> None:
    a = RandomAccessReadBuffer.from_bytes(b"abc")
    b = RandomAccessReadBuffer.from_stream(io.BytesIO(b"abc"))
    assert a.length() == 3
    assert b.length() == 3

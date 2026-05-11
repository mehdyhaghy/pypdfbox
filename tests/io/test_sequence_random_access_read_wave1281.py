"""Wave 1281: SequenceRandomAccessRead port."""

from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer, SequenceRandomAccessRead


def _seq(*parts: bytes) -> SequenceRandomAccessRead:
    return SequenceRandomAccessRead([RandomAccessReadBuffer(p) for p in parts])


def test_read_spans_multiple_sources() -> None:
    seq = _seq(b"abc", b"def", b"ghi")
    assert seq.length() == 9
    out = bytearray(9)
    n = seq.read_into(out)
    assert n == 9
    assert bytes(out) == b"abcdefghi"


def test_seek_across_boundary() -> None:
    seq = _seq(b"abc", b"def", b"ghi")
    seq.seek(4)
    assert seq.get_position() == 4
    assert seq.read() == ord("e")


def test_empty_list_rejected() -> None:
    with pytest.raises(ValueError):
        SequenceRandomAccessRead([])


def test_zero_length_readers_filtered_out() -> None:
    # All-empty inputs reduce to an empty effective list — raise.
    with pytest.raises(ValueError):
        _seq(b"", b"")


def test_eof_after_last_byte() -> None:
    seq = _seq(b"ab")
    seq.read()
    seq.read()
    assert seq.is_eof()


def test_create_view_unsupported() -> None:
    seq = _seq(b"abc")
    with pytest.raises(NotImplementedError):
        seq.create_view(0, 1)


def test_close_marks_closed() -> None:
    seq = _seq(b"abc")
    seq.close()
    assert seq.is_closed()

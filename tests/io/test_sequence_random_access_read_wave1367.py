"""Wave 1367 — :class:`SequenceRandomAccessRead` boundary coverage.

Targets cross-boundary read patterns, seek-direction heuristic
(forward / backward scans), and ``available()`` consistency across
the joined view.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.sequence_random_access_read import SequenceRandomAccessRead


def _seq(*chunks: bytes) -> SequenceRandomAccessRead:
    return SequenceRandomAccessRead([RandomAccessReadBuffer(c) for c in chunks])


def test_construction_filters_empty_readers() -> None:
    seq = _seq(b"", b"abc", b"", b"def")
    assert seq.length() == 6
    out = bytearray(6)
    n = seq.read_into(out)
    assert n == 6
    assert bytes(out) == b"abcdef"


def test_empty_list_rejected() -> None:
    with pytest.raises(ValueError):
        SequenceRandomAccessRead([])


def test_all_empty_readers_rejected() -> None:
    with pytest.raises(ValueError):
        SequenceRandomAccessRead(
            [RandomAccessReadBuffer(b""), RandomAccessReadBuffer(b"")]
        )


def test_none_list_rejected() -> None:
    with pytest.raises(ValueError):
        SequenceRandomAccessRead(None)  # type: ignore[arg-type]


def test_read_across_first_boundary() -> None:
    seq = _seq(b"abc", b"def", b"ghi")
    # Read 5 bytes that span the first/second boundary.
    out = bytearray(5)
    n = seq.read_into(out)
    assert n == 5
    assert bytes(out) == b"abcde"


def test_read_across_all_boundaries() -> None:
    seq = _seq(b"ab", b"cd", b"ef")
    out = bytearray(6)
    n = seq.read_into(out)
    assert n == 6
    assert bytes(out) == b"abcdef"
    # Subsequent read past EOF returns EOF.
    assert seq.read_into(bytearray(2)) == seq.EOF


def test_seek_forward_then_read() -> None:
    seq = _seq(b"01234", b"56789", b"abcde")
    seq.seek(7)  # inside chunk 1
    out = bytearray(5)
    seq.read_into(out)
    assert bytes(out) == b"789ab"


def test_seek_backward_then_read() -> None:
    seq = _seq(b"01234", b"56789", b"abcde")
    # Walk to end then jump back to chunk 0.
    seq.seek(12)
    seq.seek(3)  # backward jump
    out = bytearray(5)
    seq.read_into(out)
    assert bytes(out) == b"34567"


def test_seek_past_total_length_clamps_position() -> None:
    seq = _seq(b"abc", b"def")
    seq.seek(1000)
    # current_position clamps to total_length.
    assert seq.get_position() == 6
    assert seq.is_eof() is True
    assert seq.read() == seq.EOF


def test_seek_negative_raises_oserror() -> None:
    seq = _seq(b"abc")
    with pytest.raises(OSError):
        seq.seek(-1)


def test_read_single_byte_across_boundary() -> None:
    seq = _seq(b"ab", b"cd")
    # Read bytes one at a time across the boundary.
    assert seq.read() == ord("a")
    assert seq.read() == ord("b")
    assert seq.read() == ord("c")
    assert seq.read() == ord("d")
    assert seq.read() == seq.EOF
    assert seq.is_eof() is True


def test_available_reflects_position() -> None:
    seq = _seq(b"abc", b"def")
    assert seq.available() == 6
    seq.seek(2)
    assert seq.available() == 4


def test_read_into_zero_length_returns_zero() -> None:
    seq = _seq(b"abc")
    assert seq.read_into(bytearray(4), 0, 0) == 0


def test_close_propagates_to_children() -> None:
    children = [RandomAccessReadBuffer(b"abc"), RandomAccessReadBuffer(b"def")]
    seq = SequenceRandomAccessRead(children)
    seq.close()
    assert seq.is_closed() is True
    for c in children:
        assert c.is_closed() is True


def test_post_close_ops_raise() -> None:
    seq = _seq(b"abc")
    seq.close()
    with pytest.raises(OSError):
        seq.read()
    with pytest.raises(OSError):
        seq.seek(0)
    with pytest.raises(OSError):
        seq.length()
    with pytest.raises(OSError):
        seq.get_position()
    with pytest.raises(OSError):
        seq.is_eof()
    with pytest.raises(OSError):
        seq.check_closed()


def test_create_view_unsupported() -> None:
    seq = _seq(b"abc")
    with pytest.raises(NotImplementedError):
        seq.create_view(0, 2)


def test_get_current_reader_advances_past_exhausted() -> None:
    seq = _seq(b"ab", b"cd")
    out = bytearray(2)
    seq.read_into(out)  # exhaust first reader
    # Position is 2; the next get_current_reader call must advance.
    next_reader = seq.get_current_reader()
    # The new reader should be at position 0 of the second chunk.
    assert next_reader.get_position() == 0


def test_problematic_reader_in_list_raises() -> None:
    class Broken(RandomAccessReadBuffer):
        def length(self) -> int:  # type: ignore[override]
            raise OSError("broken length")

    with pytest.raises(ValueError):
        SequenceRandomAccessRead([Broken(b"abc")])

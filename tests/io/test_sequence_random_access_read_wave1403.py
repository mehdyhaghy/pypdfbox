"""Wave 1403 branch round-out for ``SequenceRandomAccessRead.seek``.

Closes 134->139 — the ``while 0 <= i < self._number_of_readers`` False exit:
the reader-locating loop normally always ``break``s on a covering sub-reader
because the constructor builds *contiguous* ``[start, end]`` ranges. The loop
can only fall through (its bounds condition going False) when a target
position lands in a gap that no reader covers — a state the contiguous-range
invariant prevents. We introduce a gap directly so the scan walks off the end
without matching, exercising the defensive fall-through to ``_current_position
= position``.
"""

from __future__ import annotations

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.sequence_random_access_read import SequenceRandomAccessRead


def test_seek_into_gap_falls_through_reader_scan() -> None:
    """Closes 134->139: with a manufactured gap in the range tables, seeking
    to an uncovered offset makes the locating loop exit via its bounds
    condition rather than ``break``; ``_current_position`` is still set."""
    seq = SequenceRandomAccessRead(
        [RandomAccessReadBuffer(b"aaaa"), RandomAccessReadBuffer(b"bbbb")]
    )
    # Contiguous by construction: starts [0,4], ends [3,7], total 8.
    # Punch a gap: make reader 0 cover [0,2] and reader 1 cover [5,7], so
    # offsets 3 and 4 are covered by nobody.
    seq._end_positions[0] = 2  # noqa: SLF001
    seq._start_positions[1] = 5  # noqa: SLF001
    seq._current_index = 0  # noqa: SLF001
    seq._current_position = 0  # noqa: SLF001

    # Seek to 4 (in the gap, and < total_length 8). The scan walks i upward
    # past reader 1 without matching, exiting the while via its bounds check.
    seq.seek(4)
    assert seq.get_position() == 4

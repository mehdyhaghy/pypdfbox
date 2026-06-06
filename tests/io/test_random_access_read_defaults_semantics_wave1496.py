"""RandomAccessRead default-method semantics (peek / rewind / skip / available
/ readFully / isEOF / SequenceRandomAccessRead bulk-read across a segment
boundary), pinned against the live Apache PDFBox 3.0.7 oracle (wave 1496).

The wave-1482 ``RandomAccessReadSemanticsProbe`` pinned closed-state and
negative-``seek`` semantics; this wave fills the gap for the *default* methods
of ``org.apache.pdfbox.io.RandomAccessRead``. Oracle-confirmed literals
(``oracle/probes/RandomAccessReadDefaultsProbe.java`` run against
``pdfbox-app-3.0.7.jar``):

* ``peek()`` at EOF returns ``-1`` and does NOT advance the position; mid-stream
  it returns the byte and leaves the position unchanged.
* ``rewind(int)`` is literally ``seek(getPosition() - n)`` with NO sign check —
  a NEGATIVE ``n`` therefore seeks *forward* (no exception). ``rewind`` past
  the start delegates to ``seek``, which throws ``IOException`` (-> ``OSError``).
* ``skip(int)`` is literally ``seek(getPosition() + n)`` with NO sign check and
  NO explicit length clamp — a negative ``n`` seeks backward, and a past-end
  ``n`` is clamped by ``seek`` to ``length()``.
* ``available()`` is ``min(length() - getPosition(), Integer.MAX_VALUE)`` cast
  to int; for reachable positions (``seek`` clamps) this equals
  ``length() - position`` and is never negative.
* ``readFully(byte[])`` past EOF throws ``EOFException`` (-> ``EOFError``).
* ``isEOF()`` does NOT advance the position.
* ``read(byte[0])`` returns ``0`` without advancing.
* ``SequenceRandomAccessRead.read(byte[], off, len)`` spanning a segment
  boundary returns the bytes from both segments in one call.

Before wave 1496, pypdfbox's ``rewind``/``skip`` raised ``ValueError`` on a
negative count and ``skip`` clamped via ``min(...)`` — both divergences from
upstream's guard-free ``seek`` delegation. The literal pins below pass WITHOUT
the oracle; a ``@requires_oracle`` differential test cross-checks live PDFBox.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.sequence_random_access_read import SequenceRandomAccessRead
from tests.oracle.harness import requires_oracle, run_probe_text


# ---------------------------------------------------------------------------
# peek
# ---------------------------------------------------------------------------
def test_peek_at_eof_returns_minus_one_without_advancing() -> None:
    b = RandomAccessReadBuffer(b"abc")
    b.seek(3)
    assert b.peek() == -1
    assert b.get_position() == 3


def test_peek_mid_does_not_advance() -> None:
    b = RandomAccessReadBuffer(b"abc")
    b.seek(1)
    assert b.peek() == ord("b")
    assert b.get_position() == 1


# ---------------------------------------------------------------------------
# rewind — no sign check; negative seeks forward
# ---------------------------------------------------------------------------
def test_rewind_negative_seeks_forward() -> None:
    b = RandomAccessReadBuffer(b"abcde")
    b.seek(3)
    b.rewind(-1)
    assert b.get_position() == 4


def test_rewind_zero_keeps_position() -> None:
    b = RandomAccessReadBuffer(b"abcde")
    b.seek(4)
    b.rewind(0)
    assert b.get_position() == 4


def test_rewind_past_start_raises_oserror() -> None:
    b = RandomAccessReadBuffer(b"abcde")
    b.seek(2)
    with pytest.raises(OSError):
        b.rewind(5)


# ---------------------------------------------------------------------------
# skip — no sign check, no min-clamp; relies on seek
# ---------------------------------------------------------------------------
def test_skip_advances() -> None:
    b = RandomAccessReadBuffer(b"abcde")
    b.seek(1)
    b.skip(2)
    assert b.get_position() == 3


def test_skip_past_end_clamps_to_length() -> None:
    b = RandomAccessReadBuffer(b"abcde")
    b.seek(1)
    b.skip(100)
    assert b.get_position() == 5


def test_skip_negative_seeks_backward() -> None:
    b = RandomAccessReadBuffer(b"abcde")
    b.seek(4)
    b.skip(-1)
    assert b.get_position() == 3


# ---------------------------------------------------------------------------
# available
# ---------------------------------------------------------------------------
def test_available_reports_remaining() -> None:
    b = RandomAccessReadBuffer(b"abcdefghij")
    assert b.available() == 10
    b.seek(4)
    assert b.available() == 6
    b.seek(10)
    assert b.available() == 0
    b.seek(100)  # clamped to length
    assert b.available() == 0


# ---------------------------------------------------------------------------
# read(byte[]) / readFully
# ---------------------------------------------------------------------------
def test_read_into_empty_buffer_returns_zero() -> None:
    b = RandomAccessReadBuffer(b"abc")
    assert b.read_into(bytearray(0)) == 0
    assert b.get_position() == 0


def test_read_fully_past_eof_raises_eoferror() -> None:
    b = RandomAccessReadBuffer(b"abc")
    with pytest.raises(EOFError):
        b.read_fully(bytearray(5))


# ---------------------------------------------------------------------------
# isEOF non-advancing
# ---------------------------------------------------------------------------
def test_is_eof_does_not_advance() -> None:
    b = RandomAccessReadBuffer(b"abc")
    b.seek(1)
    assert b.is_eof() is False
    assert b.get_position() == 1
    b.seek(3)
    assert b.is_eof() is True
    assert b.get_position() == 3


# ---------------------------------------------------------------------------
# SequenceRandomAccessRead bulk read across a segment boundary
# ---------------------------------------------------------------------------
def test_sequence_bulk_read_crosses_segment_boundary() -> None:
    seq = SequenceRandomAccessRead(
        [RandomAccessReadBuffer(b"abc"), RandomAccessReadBuffer(b"de")]
    )
    seq.seek(2)  # last byte of segment 1
    dst = bytearray(5)
    n = seq.read_into(dst, 0, 5)
    assert n == 3
    assert dst[:3] == b"cde"
    assert seq.get_position() == 5
    assert seq.read() == -1
    assert seq.available() == 0


# ---------------------------------------------------------------------------
# Live differential check against Apache PDFBox 3.0.7.
# ---------------------------------------------------------------------------
@requires_oracle
def test_oracle_matches_default_method_semantics() -> None:
    out = run_probe_text("RandomAccessReadDefaultsProbe")
    lines = dict(line.split("=", 1) for line in out.strip().splitlines())

    assert lines["peekEOF.val"] == "-1"
    assert lines["peekEOF.posAfter"] == "3"
    assert lines["peekMid.val"] == "98"
    assert lines["peekMid.posAfter"] == "1"

    assert lines["rewindPastStart"] == "java.io.IOException"
    assert lines["rewindNeg"] == "NO_THROW pos=4"
    assert lines["rewind0.pos"] == "4"

    assert lines["avail.start"] == "10"
    assert lines["avail.mid"] == "6"
    assert lines["avail.end"] == "0"
    assert lines["avail.pastEnd"] == "0"

    assert lines["skip.pos"] == "3"
    assert lines["skipPastEnd.pos"] == "5"
    assert lines["skipNeg"] == "NO_THROW pos=4"

    assert lines["readEmptyArr"] == "0"
    assert lines["readEmptyArr.pos"] == "0"
    assert lines["readArr"] == "3"
    assert lines["readArrEOF"] == "-1"

    assert lines["readFullyPastEOF"] == "java.io.EOFException"

    assert lines["isEOF.mid"] == "false"
    assert lines["isEOF.mid.posAfter"] == "1"
    assert lines["isEOF.end"] == "true"
    assert lines["isEOF.end.posAfter"] == "3"

    assert lines["seqCross.n"] == "3"
    assert lines["seqCross.bytes"] == "cde"
    assert lines["seqCross.posAfter"] == "5"
    assert lines["seqCross.readAfter"] == "-1"
    assert lines["seqCross.avail"] == "0"

"""Differential fuzz of ``RandomAccessReadBuffer`` + ``RandomAccessReadView``
edge operation sequences against the live Apache PDFBox 3.0.7 oracle (wave 1552).

The wave-1482 ``RandomAccessReadSemanticsProbe`` pinned closed-state and
negative-``seek`` exceptions; the wave-1496 ``RandomAccessReadDefaultsProbe``
pinned the default-method semantics (peek/rewind/skip/available/readFully).
This wave fuzzes the *combined operation sequences* those probes left open,
concentrating on the EOF/bounds boundary and the ``RandomAccessReadView``
window:

* single ``read()`` exactly at / after EOF (-> -1, no throw, position frozen);
* ``read(byte[], off, len)`` straddling EOF (partial count), starting AT EOF
  (-> -1), and with a non-zero destination offset;
* ``seek(length)`` (legal EOF) vs ``seek(length + 1)`` (clamp to length) vs
  ``seek(-1)`` (``OSError``);
* ``rewind`` past the start delegating to ``seek(negative)`` (-> ``OSError``);
* ``skip`` past EOF clamping, then ``skip`` again while already at EOF;
* ``peek`` at EOF / one-before-EOF leaving the position unchanged;
* ``available`` after a clamped past-end seek;
* a ``RandomAccessReadView`` whose declared length **exceeds** the parent's
  remaining bytes — the view runs off the parent before its own logical end:
  ``read`` returns a partial count and then ``-1`` while ``is_eof`` stays
  ``False`` (because ``current_position < stream_length``), exactly mirroring
  upstream ``RandomAccessReadView.read`` (EOF is decided by the parent, not the
  view's declared length);
* a view wholly inside the parent: single reads past the bounded length,
  ``seek`` clamping (note Java stores the raw ``new_offset`` even past the
  declared length — ``view.in.seekPast.pos == 100``), bulk read clipped to the
  view's ``available()``, ``rewind`` across the view origin, ``peek``, nested
  ``create_view`` (forbidden), and post-close operations;
* a view created at the parent's EOF (zero readable bytes): ``read`` -> -1 even
  though ``is_eof`` is ``False``.

Every literal below was produced by the live oracle
(``oracle/probes/RandomAccessReadFuzzProbe.java`` run against
``pdfbox-app-3.0.7.jar``). Python matched the oracle on all 50+ projected
observations — no production divergence was found, so the literals double as a
self-contained both-sides pin and the ``@requires_oracle`` test cross-checks the
live jar. Java ``java.io.IOException`` maps to Python ``OSError``.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from tests.oracle.harness import requires_oracle, run_probe_text

_DATA = b"0123456789"  # length 10


# ===========================================================================
# RandomAccessReadBuffer — EOF / seek / skip / peek / close edge sequences
# ===========================================================================
def test_buffer_read_at_and_after_eof_returns_minus_one() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(10)
    assert b.read() == -1
    assert b.get_position() == 10  # frozen at EOF
    assert b.read() == -1


def test_buffer_bulk_read_straddling_eof_is_partial() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(8)
    dst = bytearray(5)
    assert b.read_into(dst, 0, 5) == 2  # only "89" left
    assert dst[:2] == b"89"
    assert b.get_position() == 10


def test_buffer_bulk_read_starting_at_eof_returns_minus_one() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(10)
    assert b.read_into(bytearray(4), 0, 4) == -1


def test_buffer_bulk_read_with_destination_offset() -> None:
    b = RandomAccessReadBuffer(_DATA)
    dst = bytearray(8)
    assert b.read_into(dst, 3, 4) == 4
    assert dst[3:7] == b"0123"
    assert b.get_position() == 4


def test_buffer_seek_length_is_legal_eof() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(10)
    assert b.get_position() == 10
    assert b.is_eof() is True


def test_buffer_seek_past_length_clamps() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(11)
    assert b.get_position() == 10


def test_buffer_seek_negative_raises() -> None:
    b = RandomAccessReadBuffer(_DATA)
    with pytest.raises(OSError):
        b.seek(-1)


def test_buffer_rewind_over_position_raises() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(3)
    with pytest.raises(OSError):
        b.rewind(5)  # seek(-2)


def test_buffer_skip_past_eof_then_again_clamps() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(7)
    b.skip(100)
    assert b.get_position() == 10
    b.skip(100)
    assert b.get_position() == 10


def test_buffer_peek_at_eof_and_last_byte() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(10)
    assert b.peek() == -1
    assert b.get_position() == 10
    b.seek(9)
    assert b.peek() == ord("9")  # 57
    assert b.get_position() == 9


def test_buffer_available_after_clamped_seek() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.seek(100)
    assert b.available() == 0
    b.seek(6)
    assert b.available() == 4


def test_buffer_double_close_is_idempotent_then_operations_raise() -> None:
    b = RandomAccessReadBuffer(_DATA)
    b.close()
    b.close()  # idempotent
    assert b.is_closed() is True
    with pytest.raises(OSError):
        b.read()
    with pytest.raises(OSError):
        b.length()


# ===========================================================================
# RandomAccessReadView whose declared length exceeds the parent's remainder
# ===========================================================================
def test_view_past_parent_eof_reads_partial_then_minus_one() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(4, 10)  # claims 10, parent only has 6 left
    try:
        assert v.length() == 10
        assert v.available() == 10  # declared length, not parent remainder
        dst = bytearray(10)
        n = v.read_into(dst, 0, 10)
        assert n == 6  # "456789"
        assert dst[:6] == b"456789"
        assert v.get_position() == 6
        # is_eof is decided by the view's declared length, not the parent:
        # position 6 < stream_length 10, so is_eof is False even though the
        # parent is exhausted and the next read returns -1.
        assert v.is_eof() is False
        assert v.read() == -1
    finally:
        v.close()
        parent.close()


# ===========================================================================
# RandomAccessReadView wholly inside the parent ("2345")
# ===========================================================================
def test_view_inside_single_reads_past_bound() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(2, 4)  # "2345"
    try:
        vals = [v.read() for _ in range(6)]
        assert vals == [ord("2"), ord("3"), ord("4"), ord("5"), -1, -1]
        assert v.get_position() == 4
        assert v.is_eof() is True
    finally:
        v.close()
        parent.close()


def test_view_inside_seek_length_past_and_negative() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(2, 4)
    try:
        v.seek(4)
        assert v.get_position() == 4
        assert v.is_eof() is True
        # Upstream stores the raw new_offset even past the declared length;
        # only the parent seek is clamped. So get_position reports 100 here.
        v.seek(100)
        assert v.get_position() == 100
        with pytest.raises(OSError):
            v.seek(-1)
    finally:
        v.close()
        parent.close()


def test_view_inside_bulk_read_clipped_to_available() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(2, 4)
    try:
        v.seek(1)
        dst = bytearray(10)
        assert v.read_into(dst, 0, 10) == 3  # clipped to available "345"
        assert dst[:3] == b"345"
        assert v.get_position() == 4
    finally:
        v.close()
        parent.close()


def test_view_inside_rewind_over_origin_raises() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(2, 4)
    try:
        v.seek(2)
        with pytest.raises(OSError):
            v.rewind(5)  # parent seek would go negative
    finally:
        v.close()
        parent.close()


def test_view_inside_peek_eof_and_mid() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(2, 4)
    try:
        v.seek(4)
        assert v.peek() == -1
        v.seek(1)
        assert v.peek() == ord("3")  # 51
        assert v.get_position() == 1
    finally:
        v.close()
        parent.close()


def test_view_inside_nested_create_view_forbidden() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(2, 4)
    try:
        with pytest.raises(OSError):
            v.create_view(0, 1)
    finally:
        v.close()
        parent.close()


def test_view_inside_close_then_operations_raise() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(2, 4)
    v.close()
    assert v.is_closed() is True
    with pytest.raises(OSError):
        v.read()
    with pytest.raises(OSError):
        v.length()
    parent.close()


# ===========================================================================
# RandomAccessReadView created at the parent's EOF (zero readable bytes)
# ===========================================================================
def test_view_at_parent_eof_is_empty() -> None:
    parent = RandomAccessReadBuffer(_DATA)
    v = parent.create_view(10, 2)  # origin at parent EOF, declares 2
    try:
        assert v.length() == 2
        # is_eof False (position 0 < declared length 2) but no bytes readable.
        assert v.is_eof() is False
        assert v.read() == -1
        assert v.read_into(bytearray(2), 0, 2) == -1
    finally:
        v.close()
        parent.close()


# ===========================================================================
# Live differential check against Apache PDFBox 3.0.7.
# ===========================================================================
@requires_oracle
def test_oracle_matches_random_access_read_fuzz() -> None:
    out = run_probe_text("RandomAccessReadFuzzProbe")
    lines = dict(line.split("=", 1) for line in out.strip().splitlines())

    # ---- buffer ----
    assert lines["buf.readAtEOF"] == "-1"
    assert lines["buf.readAtEOF.pos"] == "10"
    assert lines["buf.readAfterEOF"] == "-1"
    assert lines["buf.readStraddle"] == "2"
    assert lines["buf.readStraddle.bytes"] == "89"
    assert lines["buf.readStraddle.pos"] == "10"
    assert lines["buf.readArrAtEOF"] == "-1"
    assert lines["buf.readArrOff"] == "4"
    assert lines["buf.readArrOff.bytes"] == "0123"
    assert lines["buf.readArrOff.pos"] == "4"
    assert lines["buf.seekLen.pos"] == "10"
    assert lines["buf.seekLen.isEOF"] == "true"
    assert lines["buf.seekPastLen.pos"] == "10"
    assert lines["buf.seekNeg"] == "java.io.IOException"
    assert lines["buf.rewindOverPos"] == "java.io.IOException"
    assert lines["buf.skipPastEOF.pos"] == "10"
    assert lines["buf.skipAtEOFagain.pos"] == "10"
    assert lines["buf.peekEOF"] == "-1"
    assert lines["buf.peekEOF.pos"] == "10"
    assert lines["buf.peekLast"] == "57"
    assert lines["buf.peekLast.pos"] == "9"
    assert lines["buf.availPastEnd"] == "0"
    assert lines["buf.availMid"] == "4"
    assert lines["buf.isClosed"] == "true"
    assert lines["buf.readClosed"] == "java.io.IOException"
    assert lines["buf.lengthClosed"] == "java.io.IOException"

    # ---- view past parent EOF ----
    assert lines["view.length"] == "10"
    assert lines["view.avail0"] == "10"
    assert lines["view.readAll"] == "6"
    assert lines["view.readAll.bytes"] == "456789"
    assert lines["view.readAll.pos"] == "6"
    assert lines["view.readAll.isEOF"] == "false"
    assert lines["view.readAll.readAfter"] == "-1"

    # ---- view inside parent ----
    assert lines["view.in.singleReads"] == "50,51,52,53,-1,-1"
    assert lines["view.in.pos"] == "4"
    assert lines["view.in.isEOF"] == "true"
    assert lines["view.in.seekLen.pos"] == "4"
    assert lines["view.in.seekLen.isEOF"] == "true"
    assert lines["view.in.seekPast.pos"] == "100"
    assert lines["view.in.seekNeg"] == "java.io.IOException"
    assert lines["view.in.readClip"] == "3"
    assert lines["view.in.readClip.bytes"] == "345"
    assert lines["view.in.readClip.pos"] == "4"
    assert lines["view.in.rewindOver"] == "java.io.IOException"
    assert lines["view.in.peekEOF"] == "-1"
    assert lines["view.in.peekMid"] == "51"
    assert lines["view.in.peekMid.pos"] == "1"
    assert lines["view.in.nested"] == "java.io.IOException"
    assert lines["view.in.isClosed"] == "true"
    assert lines["view.in.readClosed"] == "java.io.IOException"
    assert lines["view.in.lengthClosed"] == "java.io.IOException"

    # ---- view at parent EOF ----
    assert lines["view.end.length"] == "2"
    assert lines["view.end.isEOF"] == "false"
    assert lines["view.end.read"] == "-1"
    assert lines["view.end.readArr"] == "-1"

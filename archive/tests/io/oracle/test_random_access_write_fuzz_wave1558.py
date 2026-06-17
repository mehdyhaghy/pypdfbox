"""Differential fuzz of the WRITE side of the RandomAccess family against the
live Apache PDFBox 3.0.7 oracle (wave 1558).

The wave-1483 ``RandomAccessWriteScratchSemanticsProbe`` pinned the closed-state
and negative-``seek`` exceptions; wave 1552 fuzzed the *read* side
(``RandomAccessReadBuffer`` / ``RandomAccessReadView``). This wave fuzzes the
write/read round-trip operation sequences those probes left open on
``RandomAccessReadWriteBuffer`` and ``ScratchFileBuffer``:

* ``write(int)`` single bytes then ``seek(0)`` + read-back;
* ``write(byte[], off, len)`` with off/len edges (sub-slice, ``len == 0``
  no-op, whole array);
* seek-to-middle then overwrite (in-place patch) — length unchanged;
* seek **past** the current length, then write — upstream **clamps** the seek
  to the current length (no gap / zero-fill) so the byte appends at the end;
* ``length()`` / ``get_position()`` after a seek-past-end **without** writing
  (both clamp to the current length);
* ``clear()`` then ``length`` / ``get_position`` / ``read`` and write-after-clear
  reuse;
* a write spanning a 4 KiB ``ScratchFileBuffer`` page boundary, read back across
  the boundary;
* ``ScratchFileBuffer`` seek-past-end raising (``EOFError`` ≈ Java
  ``EOFException``, PDFBOX-4756);
* double-close then write/clear (``OSError`` ≈ Java ``IOException``).

Honest divergence pinned below: upstream ``RandomAccessReadWriteBuffer.write``
is a **relative** ``ByteBuffer.put`` while ``read``/``seek`` are **absolute**
``get(index)``. A ``read()`` advances the logical pointer but NOT the
ByteBuffer's relative put position, so a ``write()`` that immediately follows a
``read()`` lands at the ByteBuffer's *stale* relative position rather than at
the logical pointer. pypdfbox is backed by a single ``BytesIO`` cursor, so its
write always lands at the logical position — internally consistent, and
matching upstream on every path a real PDFBox writer exercises (sequential
writes; seek-then-write with no interleaved read). Only the read-immediately-
then-write interleave diverges; it is documented in CHANGES.md and asserted
here on both sides.

Every literal was produced by the live oracle
(``oracle/probes/RandomAccessWriteFuzzProbe.java`` run against
``pdfbox-app-3.0.7.jar``). Java ``java.io.IOException`` maps to Python
``OSError``; Java ``java.io.EOFException`` maps to Python ``EOFError``.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.random_access_read_write_buffer import RandomAccessReadWriteBuffer
from pypdfbox.io.scratch_file import ScratchFile
from tests.oracle.harness import requires_oracle, run_probe_text


def _drain(w: object) -> list[int]:
    """Read the whole buffer from position 0 as a list of unsigned bytes."""
    save = w.get_position()  # type: ignore[attr-defined]
    w.seek(0)  # type: ignore[attr-defined]
    out: list[int] = []
    while True:
        b = w.read()  # type: ignore[attr-defined]
        if b == -1:
            break
        out.append(b)
    w.seek(save)  # type: ignore[attr-defined]
    return out


# ===========================================================================
# RandomAccessReadWriteBuffer — single-byte write then read-back
# ===========================================================================
def test_rwb_single_byte_write_then_read_back() -> None:
    w = RandomAccessReadWriteBuffer()
    for ch in b"ABC":
        w.write(ch)
    assert w.length() == 3
    assert w.get_position() == 3
    w.seek(0)
    assert w.read() == 65
    assert w.read() == 66
    assert w.read() == 67
    assert w.read() == -1  # EOF
    assert w.get_position() == 3
    w.close()


# ===========================================================================
# write(byte[], off, len) edges
# ===========================================================================
def test_rwb_write_bytes_offset_length_edges() -> None:
    w = RandomAccessReadWriteBuffer()
    src = b"0123456789"
    w.write_bytes(src, 2, 4)  # "2345"
    assert w.length() == 4
    assert _drain(w) == [50, 51, 52, 53]
    # len == 0 is a no-op (length + position unchanged)
    w.write_bytes(src, 0, 0)
    assert w.length() == 4
    assert w.get_position() == 4
    # whole array appended
    w.write_bytes(src)
    assert w.length() == 14
    w.close()


# ===========================================================================
# seek-to-middle overwrite (in-place patch) — length unchanged
# ===========================================================================
def test_rwb_seek_middle_overwrite_keeps_length() -> None:
    w = RandomAccessReadWriteBuffer()
    w.write_bytes(b"ABCDEF")
    w.seek(2)
    w.write(ord("x"))
    w.write(ord("y"))
    assert w.length() == 6
    assert w.get_position() == 4
    assert _drain(w) == [65, 66, 120, 121, 69, 70]  # AB xy EF
    w.close()


def test_rwb_seek_then_write_without_read_lands_at_position() -> None:
    # seek-then-write with NO interleaved read: matches upstream exactly
    # (the ByteBuffer relative put position still tracks the logical pointer).
    w = RandomAccessReadWriteBuffer()
    w.write_bytes(b"12345")
    w.seek(2)
    w.write(ord("Z"))
    assert _drain(w) == [49, 50, 90, 52, 53]  # 1 2 Z 4 5
    assert w.get_position() == 3
    assert w.length() == 5
    w.close()


# ===========================================================================
# seek PAST end then write — upstream clamps the seek (no gap / zero-fill)
# ===========================================================================
def test_rwb_seek_past_end_then_write_clamps_and_appends() -> None:
    w = RandomAccessReadWriteBuffer()
    w.write_bytes(b"AB")  # length 2
    w.seek(5)  # clamped to length 2
    assert w.get_position() == 2
    assert w.length() == 2
    w.write(ord("Z"))
    assert w.length() == 3
    assert w.get_position() == 3
    assert _drain(w) == [65, 66, 90]  # AB Z (no zero-fill gap)
    w.close()


def test_rwb_seek_past_end_without_write_clamps() -> None:
    w = RandomAccessReadWriteBuffer()
    w.write_bytes(b"AB")
    w.seek(100)  # clamped
    assert w.get_position() == 2
    assert w.length() == 2
    w.close()


# ===========================================================================
# clear() then length / position / read, and write-after-clear reuse
# ===========================================================================
def test_rwb_clear_then_reuse() -> None:
    w = RandomAccessReadWriteBuffer()
    w.write_bytes(b"hello")
    w.clear()
    assert w.length() == 0
    assert w.get_position() == 0
    assert w.read() == -1
    w.write(ord("Q"))
    assert w.length() == 1
    assert _drain(w) == [81]
    w.close()


# ===========================================================================
# interleave write / seek / read — pins the relative/absolute divergence
# ===========================================================================
def test_rwb_interleave_write_seek_read_position_tracking() -> None:
    w = RandomAccessReadWriteBuffer()
    w.write_bytes(b"12345")
    w.seek(1)
    assert w.read() == 50  # '2', logical pointer -> 2
    w.write(ord("Z"))
    assert w.get_position() == 3  # pointer advanced (matches Java)
    assert w.read() == 52  # '4'
    assert w.length() == 5
    # DIVERGENCE: pypdfbox (single BytesIO cursor) writes Z at the logical
    # pointer (index 2) -> [49, 50, 90, 52, 53]. Upstream's relative
    # ByteBuffer.put lands Z at the stale relative position (index 1) ->
    # [49, 90, 51, 52, 53] (oracle rwb.inter.bytes). See module docstring.
    assert _drain(w) == [49, 50, 90, 52, 53]
    w.close()


def test_rwb_read_then_write_position_divergence() -> None:
    w = RandomAccessReadWriteBuffer()
    w.write_bytes(b"ABCDE")
    w.seek(0)
    w.read()  # A
    w.read()  # B -> logical pointer 2
    w.write(ord("z"))
    assert w.get_position() == 3  # pointer advanced (matches Java)
    # DIVERGENCE: pypdfbox writes z at the logical pointer (index 2) ->
    # [65, 66, 122, 68, 69]. Upstream relative put lands z at the stale
    # ByteBuffer position (index 0) -> [122, 66, 67, 68, 69]
    # (oracle rwb.readWrite.bytes). See module docstring.
    assert _drain(w) == [65, 66, 122, 68, 69]
    w.close()


# ===========================================================================
# double-close then write / clear raise
# ===========================================================================
def test_rwb_double_close_then_write_and_clear_raise() -> None:
    w = RandomAccessReadWriteBuffer()
    w.write(ord("A"))
    w.close()
    w.close()  # idempotent
    with pytest.raises(OSError):
        w.write(ord("B"))
    with pytest.raises(OSError):
        w.clear()


# ===========================================================================
# ScratchFileBuffer — write spanning a 4 KiB page boundary
# ===========================================================================
def test_scratch_buffer_write_spans_page_boundary() -> None:
    sf = ScratchFile.get_main_memory_only_instance()
    try:
        buf = sf.create_buffer()
        buf.write_bytes(b"a" * 4090)
        buf.write_bytes(b"b" * 12)  # crosses into page 2
        assert buf.length() == 4102
        assert buf.get_position() == 4102
        buf.seek(4088)
        window = bytearray(14)
        n = buf.read_into(window, 0, 14)
        assert n == 14
        assert window[:n] == b"aabbbbbbbbbbbb"
        buf.seek(buf.length())
        assert buf.read() == -1  # EOF
        buf.close()
    finally:
        sf.close()


# ===========================================================================
# ScratchFileBuffer — seek-to-middle overwrite + seek-past-end raises
# ===========================================================================
def test_scratch_buffer_patch_and_seek_past_end_raises() -> None:
    sf = ScratchFile.get_main_memory_only_instance()
    try:
        buf = sf.create_buffer()
        buf.write_bytes(b"ABCDEF")
        buf.seek(2)
        buf.write(ord("x"))
        assert buf.length() == 6
        assert buf.get_position() == 3
        assert _drain(buf) == [65, 66, 120, 68, 69, 70]  # AB x DEF
        # Unlike RandomAccessReadWriteBuffer (which clamps), ScratchFileBuffer
        # raises EOFError on seek-past-end (Java EOFException, PDFBOX-4756).
        with pytest.raises(EOFError):
            buf.seek(100)
        buf.close()
    finally:
        sf.close()


# ===========================================================================
# ScratchFileBuffer — clear() then reuse
# ===========================================================================
def test_scratch_buffer_clear_then_reuse() -> None:
    sf = ScratchFile.get_main_memory_only_instance()
    try:
        buf = sf.create_buffer()
        buf.write_bytes(b"hello")
        buf.clear()
        assert buf.length() == 0
        assert buf.get_position() == 0
        assert buf.read() == -1
        buf.write(ord("Q"))
        assert buf.length() == 1
        assert _drain(buf) == [81]
        buf.close()
    finally:
        sf.close()


# ===========================================================================
# Live differential check against Apache PDFBox 3.0.7.
# ===========================================================================
@requires_oracle
def test_oracle_matches_random_access_write_fuzz() -> None:
    out = run_probe_text("RandomAccessWriteFuzzProbe")
    lines = dict(line.split("=", 1) for line in out.strip().splitlines())

    # ---- single-byte write + read-back ----
    assert lines["rwb.afterWrite.len"] == "3"
    assert lines["rwb.afterWrite.pos"] == "3"
    assert lines["rwb.read0"] == "65"
    assert lines["rwb.read1"] == "66"
    assert lines["rwb.read2"] == "67"
    assert lines["rwb.readEOF"] == "-1"
    assert lines["rwb.eof.pos"] == "3"

    # ---- write(byte[], off, len) edges ----
    assert lines["rwb.partial.len"] == "4"
    assert lines["rwb.partial.bytes"] == "50,51,52,53"
    assert lines["rwb.zerolen.len"] == "4"
    assert lines["rwb.zerolen.pos"] == "4"
    assert lines["rwb.full.len"] == "14"

    # ---- seek-to-middle overwrite ----
    assert lines["rwb.patch.len"] == "6"
    assert lines["rwb.patch.pos"] == "4"
    assert lines["rwb.patch.bytes"] == "65,66,120,121,69,70"

    # ---- seek-past-end then write (clamp, no gap) ----
    assert lines["rwb.seekPast.pos"] == "2"
    assert lines["rwb.seekPast.len"] == "2"
    assert lines["rwb.gapWrite.len"] == "3"
    assert lines["rwb.gapWrite.pos"] == "3"
    assert lines["rwb.gapWrite.bytes"] == "65,66,90"

    # ---- seek-past-end without write (clamp) ----
    assert lines["rwb.seekNoWrite.pos"] == "2"
    assert lines["rwb.seekNoWrite.len"] == "2"

    # ---- clear + reuse ----
    assert lines["rwb.clear.len"] == "0"
    assert lines["rwb.clear.pos"] == "0"
    assert lines["rwb.clear.read"] == "-1"
    assert lines["rwb.clearReuse.len"] == "1"
    assert lines["rwb.clearReuse.bytes"] == "81"

    # ---- interleave write/seek/read (DIVERGENT bytes documented) ----
    assert lines["rwb.inter.read1"] == "50"
    assert lines["rwb.inter.pos"] == "3"
    assert lines["rwb.inter.read3"] == "52"
    assert lines["rwb.inter.len"] == "5"
    # Java relative-put quirk: Z lands at index 1. pypdfbox lands it at index 2.
    assert lines["rwb.inter.bytes"] == "49,90,51,52,53"

    # ---- seek-then-write WITHOUT read (matches pypdfbox) ----
    assert lines["rwb.seekWrite.bytes"] == "49,50,90,52,53"
    assert lines["rwb.seekWrite.pos"] == "3"
    assert lines["rwb.seekWrite.len"] == "5"

    # ---- read-then-write quirk (DIVERGENT bytes documented) ----
    # Java relative-put quirk: z lands at index 0. pypdfbox lands it at index 2.
    assert lines["rwb.readWrite.bytes"] == "122,66,67,68,69"
    assert lines["rwb.readWrite.pos"] == "3"

    # ---- ScratchFileBuffer page-boundary span ----
    assert lines["sfb.span.len"] == "4102"
    assert lines["sfb.span.pos"] == "4102"
    assert lines["sfb.span.window.n"] == "14"
    assert lines["sfb.span.window"] == "aabbbbbbbbbbbb"
    assert lines["sfb.span.readEOF"] == "-1"

    # ---- ScratchFileBuffer patch + seek-past-end raises ----
    assert lines["sfb.patch.len"] == "6"
    assert lines["sfb.patch.pos"] == "3"
    assert lines["sfb.patch.bytes"] == "65,66,120,68,69,70"
    assert lines["sfb.seekPast"] == "java.io.EOFException"

    # ---- ScratchFileBuffer clear + reuse ----
    assert lines["sfb.clear.len"] == "0"
    assert lines["sfb.clear.pos"] == "0"
    assert lines["sfb.clear.read"] == "-1"
    assert lines["sfb.clearReuse.len"] == "1"
    assert lines["sfb.clearReuse.bytes"] == "81"

    # ---- closed-state ----
    assert lines["rwb.writeAfterClose"] == "java.io.IOException"
    assert lines["rwb.clearAfterClose"] == "java.io.IOException"

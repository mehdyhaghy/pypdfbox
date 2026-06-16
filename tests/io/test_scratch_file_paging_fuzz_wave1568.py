"""Wave 1568 fuzz/parity battery for the io paging + windowing surface.

Hammers behavioral parity with Apache PDFBox 3.0.7 across three classes:

* ``ScratchFile`` — page allocation / free / reuse, write across 4 KiB page
  boundaries, short-write zero-padding, file-backed (TEMP_FILE_ONLY) and
  spill (MIXED) page storage, free-page LIFO queue, reuse zero-fill.
* ``RandomAccessReadView`` — sub-view windowing, bounds clamping at view EOF
  and parent EOF, seek past view length, rewind, ``available()`` clipping,
  nested ``create_view`` refusal.
* ``RandomAccessReadBuffer`` — read()/read_into() at EOF returning -1 (not 0),
  zero-length read returning 0 even at EOF, peek/rewind not corrupting the
  cursor, length after writes (via the write-buffer), close() idempotency.

Upstream invariants asserted here (see RandomAccessRead.java / ScratchFile.java
/ RandomAccessReadView.java in PDFBox 3.0):

* single-byte ``read()`` returns ``-1`` at EOF; ``read(b, off, len)`` returns
  ``-1`` at EOF for ``len > 0`` but ``0`` for ``len == 0``;
* ``seek`` past length clamps to length on a plain buffer but raises
  ``EOFException`` (-> ``EOFError``) on a ``ScratchFileBuffer`` (PDFBOX-4756);
* a reused freed page is zero-filled (no stale content leak);
* a ``RandomAccessReadView`` never reads past parent EOF nor past its own
  declared ``stream_length``.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.random_access_read_view import RandomAccessReadView
from pypdfbox.io.scratch_file import NO_FREE_PAGE, ScratchFile

# ----------------------------------------------------------------------
# ScratchFile page allocation / free / reuse
# ----------------------------------------------------------------------


def test_get_new_page_indices_are_monotonic_until_freed() -> None:
    sf = ScratchFile(page_size=16)
    try:
        pages = [sf.get_new_page() for _ in range(5)]
        assert pages == [0, 1, 2, 3, 4]
        assert sf.get_page_count() == 5
    finally:
        sf.close()


def test_freed_page_is_reused_lifo() -> None:
    sf = ScratchFile(page_size=16)
    try:
        p0, p1, p2 = (sf.get_new_page() for _ in range(3))
        sf.mark_pages_as_free([p0, p1])
        # Free queue is LIFO: last appended (p1) pops first.
        assert sf.get_new_page() == p1
        assert sf.get_new_page() == p0
        # Page count never shrinks on free/reuse.
        assert sf.get_page_count() == 3
        assert p2 == 2
    finally:
        sf.close()


def test_reused_page_is_zero_filled() -> None:
    sf = ScratchFile(page_size=16)
    try:
        p = sf.get_new_page()
        sf.write_page(p, bytes([0xAA] * 16))
        sf.mark_pages_as_free([p])
        p2 = sf.get_new_page()
        assert p2 == p
        out = bytearray(16)
        sf.read_page(p2, out)
        assert bytes(out) == bytes(16)
    finally:
        sf.close()


def test_mark_pages_as_free_ignores_out_of_range_and_dupes() -> None:
    sf = ScratchFile(page_size=16)
    try:
        sf.get_new_page()
        # Out-of-range and negative indices are silently ignored (upstream
        # BitSet.set on an unknown index is defensive).
        sf.mark_pages_as_free([99, -3])
        # Duplicate free of the same page is idempotent.
        sf.mark_pages_as_free([0])
        sf.mark_pages_as_free([0])
        assert sf.get_new_page() == 0
        # Only one page was ever freed despite the double-free.
        assert sf.dequeue_page() == NO_FREE_PAGE
    finally:
        sf.close()


def test_enqueue_dequeue_free_queue() -> None:
    sf = ScratchFile(page_size=16)
    try:
        assert sf.dequeue_page() == NO_FREE_PAGE
        a, b = sf.get_new_page(), sf.get_new_page()
        sf.enqueue_page(a)
        sf.enqueue_page(b)
        assert sf.dequeue_page() == b
        assert sf.dequeue_page() == a
        assert sf.dequeue_page() == NO_FREE_PAGE
    finally:
        sf.close()


# ----------------------------------------------------------------------
# ScratchFile read_page / write_page (direct page API)
# ----------------------------------------------------------------------


def test_write_page_short_write_zero_pads() -> None:
    sf = ScratchFile(page_size=16)
    try:
        p = sf.get_new_page()
        sf.write_page(p, b"hello", 0, 5)
        out = bytearray(16)
        sf.read_page(p, out)
        assert out[:5] == b"hello"
        assert bytes(out[5:]) == bytes(11)
    finally:
        sf.close()


def test_write_page_full_round_trip() -> None:
    sf = ScratchFile(page_size=16)
    try:
        p = sf.get_new_page()
        payload = bytes(range(16))
        sf.write_page(p, payload)
        out = bytearray(16)
        assert sf.read_page(p, out) == 16
        assert bytes(out) == payload
    finally:
        sf.close()


def test_write_page_length_exceeding_page_size_rejected() -> None:
    sf = ScratchFile(page_size=16)
    try:
        with pytest.raises(ValueError):
            sf.write_page(sf.get_new_page(), bytes(32), 0, 32)
    finally:
        sf.close()


def test_read_write_page_out_of_range_index() -> None:
    sf = ScratchFile(page_size=16)
    try:
        sf.get_new_page()  # only page 0 exists
        with pytest.raises(IndexError):
            sf.write_page(5, bytes(16))
        with pytest.raises(IndexError):
            sf.read_page(5, bytearray(16))
    finally:
        sf.close()


@pytest.mark.parametrize(
    "mode",
    ["main", "temp", "mixed"],
    ids=["main_memory_only", "temp_file_only", "mixed_spill"],
)
def test_page_round_trip_across_storage_modes(mode: str) -> None:
    if mode == "main":
        setting = MemoryUsageSetting.setup_main_memory_only()
    elif mode == "temp":
        setting = MemoryUsageSetting.setup_temp_file_only()
    else:
        # Cap allows only 2 pages of 16 bytes in RAM; rest spill to disk.
        setting = MemoryUsageSetting.setup_mixed(max_main_memory_bytes=32)
    sf = ScratchFile(setting, page_size=16)
    try:
        pages = [sf.get_new_page() for _ in range(6)]
        payloads = {p: bytes((p * 13 + i) % 256 for i in range(16)) for p in pages}
        for p, payload in payloads.items():
            sf.write_page(p, payload)
        for p, payload in payloads.items():
            out = bytearray(16)
            sf.read_page(p, out)
            assert bytes(out) == payload, f"page {p} corrupt in {mode}"
    finally:
        sf.close()


# ----------------------------------------------------------------------
# ScratchFileBuffer: writing across page boundaries + seek + EOF
# ----------------------------------------------------------------------


@pytest.mark.parametrize("total", [0, 1, 15, 16, 17, 48, 49, 100, 4097])
def test_buffer_write_read_round_trip(total: int) -> None:
    sf = ScratchFile(page_size=16)
    try:
        buf = sf.create_buffer()
        data = bytes((i * 31) % 256 for i in range(total))
        if data:
            buf.write_bytes(data)
        assert buf.length() == total
        buf.seek(0)
        out = bytearray(total) if total else bytearray(0)
        got = 0
        while got < total:
            n = buf.read_into(out, got, total - got)
            assert n > 0
            got += n
        assert bytes(out) == data
    finally:
        sf.close()


def test_buffer_cross_page_partial_read() -> None:
    sf = ScratchFile(page_size=16)
    try:
        buf = sf.create_buffer()
        buf.write_bytes(bytes(range(50)))
        buf.seek(14)  # 2 bytes before the first page boundary
        out = bytearray(8)
        n = buf.read_into(out, 0, 8)
        assert n == 8
        assert list(out) == list(range(14, 22))
    finally:
        sf.close()


def test_buffer_read_at_eof_returns_minus_one() -> None:
    sf = ScratchFile(page_size=16)
    try:
        buf = sf.create_buffer()
        buf.write_bytes(b"abc")
        buf.seek(3)
        assert buf.read() == RandomAccessReadBuffer.EOF
        assert buf.read_into(bytearray(5)) == RandomAccessReadBuffer.EOF
        # Zero-length read at EOF returns 0, not -1 (Java parity).
        assert buf.read_into(bytearray(5), 0, 0) == 0
    finally:
        sf.close()


def test_buffer_seek_past_length_raises_eoferror() -> None:
    sf = ScratchFile(page_size=16)
    try:
        buf = sf.create_buffer()
        buf.write_bytes(b"hello")
        # PDFBOX-4756: ScratchFileBuffer.seek past length raises EOFException.
        with pytest.raises(EOFError):
            buf.seek(6)
        # Seeking exactly to length is allowed (EOF position).
        buf.seek(5)
        assert buf.is_eof()
    finally:
        sf.close()


def test_buffer_negative_seek_raises_oserror() -> None:
    sf = ScratchFile(page_size=16)
    try:
        buf = sf.create_buffer()
        buf.write_bytes(b"hello")
        with pytest.raises(OSError):
            buf.seek(-1)
    finally:
        sf.close()


def test_buffer_overwrite_mid_stream_preserves_neighbours() -> None:
    sf = ScratchFile(page_size=16)
    try:
        buf = sf.create_buffer()
        buf.write_bytes(bytes(range(40)))
        buf.seek(10)
        buf.write_bytes(b"\xff\xff\xff")  # overwrite bytes 10,11,12
        buf.seek(0)
        out = bytearray(40)
        buf.read_into(out, 0, 40)
        expected = bytearray(range(40))
        expected[10:13] = b"\xff\xff\xff"
        assert bytes(out) == bytes(expected)
    finally:
        sf.close()


def test_buffer_clear_resets_length_and_position() -> None:
    sf = ScratchFile(page_size=16)
    try:
        buf = sf.create_buffer()
        buf.write_bytes(bytes(range(40)))
        buf.clear()
        assert buf.length() == 0
        assert buf.get_position() == 0
        assert buf.is_empty()
        buf.write_bytes(b"new")
        assert buf.length() == 3
    finally:
        sf.close()


def test_closing_scratch_file_closes_buffers() -> None:
    sf = ScratchFile(page_size=16)
    buf = sf.create_buffer()
    buf.write_bytes(b"data")
    sf.close()
    assert buf.is_closed()
    with pytest.raises(OSError):
        buf.read()


def test_scratch_file_close_idempotent() -> None:
    sf = ScratchFile(page_size=16)
    sf.close()
    sf.close()  # second close must not raise
    assert sf.is_closed()
    with pytest.raises(OSError):
        sf.get_new_page()


# ----------------------------------------------------------------------
# RandomAccessReadView windowing
# ----------------------------------------------------------------------


def test_view_windows_subrange() -> None:
    parent = RandomAccessReadBuffer(bytes(range(20)))
    try:
        view = parent.create_view(5, 8)  # bytes [5, 13)
        assert view.length() == 8
        out = bytearray(8)
        assert view.read_into(out, 0, 8) == 8
        assert list(out) == list(range(5, 13))
        assert view.is_eof()
    finally:
        parent.close()


def test_view_read_clamps_at_view_eof() -> None:
    parent = RandomAccessReadBuffer(bytes(range(20)))
    try:
        view = parent.create_view(5, 4)  # bytes [5, 9)
        out = bytearray(20)
        n = view.read_into(out, 0, 20)  # ask for more than the window
        assert n == 4
        assert list(out[:4]) == [5, 6, 7, 8]
        assert view.read() == RandomAccessReadView.EOF
        assert view.read_into(bytearray(5)) == RandomAccessReadView.EOF
    finally:
        parent.close()


def test_view_read_clamps_at_parent_eof() -> None:
    parent = RandomAccessReadBuffer(b"abc")  # 3 bytes
    try:
        # Window claims 10 bytes but parent only has 1 byte at offset 2.
        view = parent.create_view(2, 10)
        out = bytearray(10)
        first = view.read_into(out, 0, 10)
        assert first == 1
        assert out[0] == ord("c")
        # Parent exhausted: subsequent reads return -1 even though the view's
        # logical position (1) is below its declared length (10).
        assert view.read_into(bytearray(10), 0, 10) == RandomAccessReadView.EOF
        assert view.read() == RandomAccessReadView.EOF
    finally:
        parent.close()


def test_view_single_byte_read_and_position() -> None:
    parent = RandomAccessReadBuffer(bytes(range(20)))
    try:
        view = parent.create_view(3, 5)  # bytes [3, 8)
        assert view.read() == 3
        assert view.get_position() == 1
        assert view.read() == 4
        assert view.get_position() == 2
    finally:
        parent.close()


def test_view_seek_within_and_past_window() -> None:
    parent = RandomAccessReadBuffer(bytes(range(20)))
    try:
        view = parent.create_view(2, 5)  # bytes [2, 7)
        view.seek(3)
        assert view.get_position() == 3
        assert view.read() == 2 + 3  # parent byte 5
        # Seeking past the window keeps currentPosition == newOffset (upstream),
        # leaves the view at EOF, and read() returns -1.
        view.seek(100)
        assert view.get_position() == 100
        assert view.is_eof()
        assert view.read() == RandomAccessReadView.EOF
        # Negative seek is rejected.
        with pytest.raises(OSError):
            view.seek(-1)
    finally:
        parent.close()


def test_view_rewind_moves_back() -> None:
    parent = RandomAccessReadBuffer(bytes(range(20)))
    try:
        view = parent.create_view(5, 10)
        view.seek(6)
        view.rewind(3)
        assert view.get_position() == 3
        assert view.read() == 5 + 3  # parent byte 8
    finally:
        parent.close()


def test_view_available_clips_to_window() -> None:
    parent = RandomAccessReadBuffer(bytes(range(20)))
    try:
        view = parent.create_view(2, 5)
        assert view.available() == 5
        view.seek(4)
        assert view.available() == 1
        view.seek(5)
        assert view.available() == 0
    finally:
        parent.close()


def test_view_zero_length_read_returns_zero_even_at_eof() -> None:
    parent = RandomAccessReadBuffer(b"abc")
    try:
        view = parent.create_view(0, 3)
        view.seek(3)  # at view EOF
        assert view.is_eof()
        # Java read(b, off, 0) returns 0 even at EOF.
        assert view.read_into(bytearray(4), 0, 0) == 0
    finally:
        parent.close()


def test_nested_view_creation_refused() -> None:
    parent = RandomAccessReadBuffer(bytes(range(20)))
    try:
        view = parent.create_view(2, 8)
        with pytest.raises(OSError):
            view.create_view(0, 4)
    finally:
        parent.close()


def test_view_operations_after_close_raise() -> None:
    parent = RandomAccessReadBuffer(bytes(range(20)))
    view = RandomAccessReadView(parent, 2, 8, close_input=True)
    view.close()
    assert view.is_closed()
    with pytest.raises(OSError):
        view.get_position()
    with pytest.raises(OSError):
        view.seek(0)
    # Closing the view with close_input=True also closed the parent.
    assert parent.is_closed()


# ----------------------------------------------------------------------
# RandomAccessReadBuffer EOF / peek / rewind / length / close
# ----------------------------------------------------------------------


def test_buffer_read_at_eof_returns_minus_one_not_zero() -> None:
    buf = RandomAccessReadBuffer(b"abc")
    try:
        buf.seek(3)
        assert buf.read() == RandomAccessReadBuffer.EOF
        assert buf.read_into(bytearray(8)) == RandomAccessReadBuffer.EOF
        assert buf.read_into(bytearray(8), 0, 0) == 0  # zero-length -> 0
    finally:
        buf.close()


def test_buffer_seek_past_length_clamps_to_end() -> None:
    buf = RandomAccessReadBuffer(b"abc")
    try:
        # Plain buffer clamps a past-end seek (unlike ScratchFileBuffer).
        buf.seek(100)
        assert buf.get_position() == 3
        assert buf.is_eof()
        with pytest.raises(OSError):
            buf.seek(-1)
    finally:
        buf.close()


def test_buffer_peek_does_not_advance() -> None:
    buf = RandomAccessReadBuffer(b"abc")
    try:
        buf.seek(1)
        assert buf.peek() == ord("b")
        assert buf.get_position() == 1  # peek restored position
        assert buf.read() == ord("b")
        assert buf.get_position() == 2
    finally:
        buf.close()


def test_buffer_peek_at_eof_does_not_advance() -> None:
    buf = RandomAccessReadBuffer(b"q")
    try:
        buf.seek(1)
        assert buf.peek() == RandomAccessReadBuffer.EOF
        assert buf.get_position() == 1
    finally:
        buf.close()


def test_buffer_rewind_then_reread() -> None:
    buf = RandomAccessReadBuffer(bytes(range(10)))
    try:
        buf.seek(7)
        buf.rewind(4)
        assert buf.get_position() == 3
        assert buf.read() == 3
        # Rewinding past the start surfaces an OSError from seek(-n).
        buf.seek(2)
        with pytest.raises(OSError):
            buf.rewind(5)
    finally:
        buf.close()


def test_buffer_available_and_length() -> None:
    data = bytes(range(13))
    buf = RandomAccessReadBuffer(data)
    try:
        assert buf.length() == 13
        assert buf.available() == 13
        buf.seek(5)
        assert buf.available() == 8
        buf.seek(13)
        assert buf.available() == 0
    finally:
        buf.close()


def test_buffer_close_idempotent_and_guards() -> None:
    buf = RandomAccessReadBuffer(b"xyz")
    buf.close()
    buf.close()  # idempotent
    assert buf.is_closed()
    for op in (buf.read, buf.length, buf.get_position):
        with pytest.raises(OSError):
            op()
    with pytest.raises(OSError):
        buf.seek(0)


def test_buffer_read_fully_raises_eoferror_past_end() -> None:
    buf = RandomAccessReadBuffer(b"abc")
    try:
        out = bytearray(5)
        with pytest.raises(EOFError):
            buf.read_fully(out)
    finally:
        buf.close()


# ----------------------------------------------------------------------
# Randomised differential fuzz: ScratchFileBuffer vs a plain bytearray model
# ----------------------------------------------------------------------


@pytest.mark.parametrize("seed", list(range(8)))
def test_scratch_buffer_matches_model_under_random_ops(seed: int) -> None:
    rng = random.Random(seed)
    page_size = rng.choice([4, 16, 64])
    sf = ScratchFile(page_size=page_size)
    try:
        buf = sf.create_buffer()
        model = bytearray()
        for _ in range(40):
            op = rng.random()
            if op < 0.5:
                # Write at the current position (extends or overwrites).
                pos = buf.get_position()
                chunk = bytes(rng.randrange(256) for _ in range(rng.randint(0, page_size * 2)))
                buf.write_bytes(chunk)
                # Mirror onto the model.
                end = pos + len(chunk)
                if end > len(model):
                    model.extend(bytes(end - len(model)))
                model[pos:end] = chunk
            elif op < 0.8 and model:
                # Seek somewhere valid and read.
                target = rng.randint(0, len(model))
                buf.seek(target)
                n = rng.randint(0, len(model) - target + 3)
                out = bytearray(n)
                got = buf.read_into(out, 0, n) if n else 0
                avail = len(model) - target
                if n == 0:
                    assert got == 0
                elif avail == 0:
                    assert got == RandomAccessReadBuffer.EOF
                else:
                    assert got == min(n, avail)
                    assert bytes(out[:got]) == bytes(model[target : target + got])
            else:
                assert buf.length() == len(model)
        assert buf.length() == len(model)
        buf.seek(0)
        out = bytearray(len(model))
        got = 0
        while got < len(model):
            n = buf.read_into(out, got, len(model) - got)
            assert n > 0
            got += n
        assert bytes(out) == bytes(model)
    finally:
        sf.close()

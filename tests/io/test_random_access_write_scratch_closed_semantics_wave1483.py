"""Write-capable + scratch-file RandomAccess closed / negative-seek semantics,
pinned against the live Apache PDFBox 3.0.7 oracle (wave 1483 — sibling of the
wave-1482 read-family pins).

Oracle-confirmed literals
(``oracle/probes/RandomAccessWriteScratchSemanticsProbe.java`` run against
``pdfbox-app-3.0.7.jar``):

* ``RandomAccessReadMemoryMapped(File)``
  (upstream ``RandomAccessReadMemoryMappedFile``):
    - operations after ``close()`` throw
      ``IOException(getSimpleName() + " already closed")`` ->
      ``OSError("RandomAccessReadMemoryMappedFile already closed")``;
    - negative ``seek`` throws ``IOException("Invalid position " + position)`` ->
      ``OSError("Invalid position -1")``;
    - ``seek(past_end)`` clamps the position to ``length()`` and leaves the
      stream at EOF (``read()`` -> -1).
* ``RandomAccessWriteBuffer`` (upstream in-memory ``RandomAccessReadWriteBuffer``
  inherits ``checkClosed`` from ``RandomAccessReadBuffer``):
    - operations after ``close()`` throw
      ``IOException("RandomAccessBuffer already closed")`` -> ``OSError``.
* ``ScratchFile``:
    - ``create_buffer()`` (and page API) after ``close()`` throw
      ``IOException("Scratch file already closed")`` -> ``OSError``.
* ``ScratchFileBuffer``:
    - operations after ``close()`` throw
      ``IOException("Buffer already closed")`` -> ``OSError``;
    - negative ``seek`` throws ``IOException("Negative seek offset: " + pos)`` ->
      ``OSError``;
    - ``length()`` does NOT check closed (upstream Java line 134): it returns the
      cached size even after ``close()``.

These pins are literal-valued so they pass WITHOUT the oracle; a separate
``@requires_oracle`` differential test cross-checks against live PDFBox.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.io.random_access_read_memory_mapped import RandomAccessReadMemoryMapped
from pypdfbox.io.random_access_write_buffer import RandomAccessWriteBuffer
from pypdfbox.io.scratch_file import ScratchFile
from tests.oracle.harness import requires_oracle, run_probe_text

_MMAP_CLOSED = "RandomAccessReadMemoryMappedFile already closed"
_WBUF_CLOSED = "RandomAccessBuffer already closed"
_SCRATCH_CLOSED = "Scratch file already closed"
_SBUF_CLOSED = "Buffer already closed"


def _tmp(data: bytes) -> Path:
    fd, name = tempfile.mkstemp(suffix=".bin")
    os.write(fd, data)
    os.close(fd)
    return Path(name)


# ---------------------------------------------------------------------------
# RandomAccessReadMemoryMapped — closed ops + negative/past-end seek.
# ---------------------------------------------------------------------------


def test_mmap_negative_seek_message() -> None:
    p = _tmp(b"abc")
    try:
        r = RandomAccessReadMemoryMapped(p)
        try:
            with pytest.raises(OSError, match=r"Invalid position -1"):
                r.seek(-1)
        finally:
            r.close()
    finally:
        p.unlink()


def test_mmap_closed_ops_raise_oserror() -> None:
    p = _tmp(b"abc")
    try:
        r = RandomAccessReadMemoryMapped(p)
        r.close()
        for op in (r.read, lambda: r.seek(0), r.get_position, r.length):
            with pytest.raises(OSError) as exc:
                op()
            assert str(exc.value) == _MMAP_CLOSED
    finally:
        p.unlink()


def test_mmap_seek_past_end_clamps_and_reads_eof() -> None:
    p = _tmp(b"abc")
    try:
        r = RandomAccessReadMemoryMapped(p)
        try:
            r.seek(100)
            assert r.get_position() == 3
            assert r.read() == RandomAccessReadMemoryMapped.EOF
        finally:
            r.close()
    finally:
        p.unlink()


# ---------------------------------------------------------------------------
# RandomAccessWriteBuffer — closed ops.
# ---------------------------------------------------------------------------


def test_write_buffer_closed_ops_raise_oserror() -> None:
    w = RandomAccessWriteBuffer()
    w.close()
    for op in (
        lambda: w.write(0x41),
        lambda: w.write_bytes(b"x"),
        w.clear,
        w.length,
        w.is_empty,
        w.tell,
        w.to_bytes,
    ):
        with pytest.raises(OSError, match=_WBUF_CLOSED):
            op()


# ---------------------------------------------------------------------------
# ScratchFile — closed create_buffer + page API.
# ---------------------------------------------------------------------------


def test_scratch_file_closed_ops_raise_oserror() -> None:
    sf = ScratchFile()
    sf.close()
    for op in (
        sf.create_buffer,
        sf.get_new_page,
        lambda: sf.read_page(0, bytearray(sf.page_size)),
        lambda: sf.write_page(0, b"x" * sf.page_size),
    ):
        with pytest.raises(OSError, match=_SCRATCH_CLOSED):
            op()


# ---------------------------------------------------------------------------
# ScratchFileBuffer — closed ops, negative seek, unguarded length().
# ---------------------------------------------------------------------------


def test_scratch_buffer_negative_seek_message() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"abc")
        with pytest.raises(OSError, match=r"Negative seek offset: -1"):
            buf.seek(-1)


def test_scratch_buffer_closed_ops_raise_oserror() -> None:
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"abc")
        buf.close()
        for op in (
            lambda: buf.write(0x41),
            buf.read,
            lambda: buf.seek(0),
            buf.get_position,
        ):
            with pytest.raises(OSError, match=_SBUF_CLOSED):
                op()


def test_scratch_buffer_length_does_not_check_closed() -> None:
    # Upstream ScratchFileBuffer.length() (Java line 134) does NOT call
    # checkClosed(): it returns the cached size even after close().
    with ScratchFile() as sf:
        buf = sf.create_buffer()
        buf.write_bytes(b"abcde")
        assert buf.length() == 5
        buf.close()
        assert buf.length() == 5  # no raise post-close


# ---------------------------------------------------------------------------
# Differential cross-check against live PDFBox.
# ---------------------------------------------------------------------------


@requires_oracle
def test_oracle_matches_write_scratch_closed_semantics() -> None:
    out = run_probe_text("RandomAccessWriteScratchSemanticsProbe")
    lines = dict(line.split("=", 1) for line in out.strip().splitlines())

    # mmap negative seek + closed ops.
    assert lines["mmap.seekNeg"] == "java.io.IOException|Invalid position -1"
    for key in ("readClosed", "seekClosed", "getPosClosed", "lengthClosed", "isEOFClosed"):
        assert (
            lines[f"mmap.{key}"]
            == f"java.io.IOException|{_MMAP_CLOSED}"
        )
    assert lines["mmap.seekPastEnd.pos"] == "3"
    assert lines["mmap.seekPastEnd.isEOF"] == "true"
    assert lines["mmap.seekPastEnd.read"] == "-1"

    # write buffer negative seek + closed ops (RandomAccessReadWriteBuffer).
    assert lines["rwbuf.seekNeg"] == "java.io.IOException|Invalid position -1"
    for key in ("writeClosed", "writeBytesClosed", "clearClosed", "readClosed", "lengthClosed"):
        assert lines[f"rwbuf.{key}"] == f"java.io.IOException|{_WBUF_CLOSED}"

    # scratch buffer negative seek + closed ops + unguarded length().
    assert lines["sbuf.seekNeg"] == "java.io.IOException|Negative seek offset: -1"
    for key in ("writeBufClosed", "readBufClosed", "seekBufClosed", "getPosBufClosed"):
        assert lines[f"sbuf.{key}"] == f"java.io.IOException|{_SBUF_CLOSED}"
    assert lines["sbuf.lengthBufClosed"] == "NO_THROW"

    # scratch file closed createBuffer.
    assert lines["sf.createBufferClosed"] == f"java.io.IOException|{_SCRATCH_CLOSED}"

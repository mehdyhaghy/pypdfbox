"""RandomAccessRead-family closed / negative-seek semantics, pinned against
the live Apache PDFBox 3.0.7 oracle (wave 1482).

Oracle-confirmed literals (``oracle/probes/RandomAccessReadSemanticsProbe.java``
run against ``pdfbox-app-3.0.7.jar``):

* Negative ``seek`` throws ``IOException("Invalid position " + position)`` for
  ALL four classes -> ``OSError`` with message ``"Invalid position -1"``.
* Operations after ``close()`` throw ``IOException`` -> ``OSError``:
    - ``RandomAccessReadBuffer``        -> ``"RandomAccessBuffer already closed"``
    - ``RandomAccessReadBufferedFile``  -> ``"org.apache.pdfbox.io."
                                            "RandomAccessReadBufferedFile already closed"``
    - ``SequenceRandomAccessRead``      -> ``"RandomAccessBuffer already closed"``
    - ``RandomAccessReadView``          -> ``"RandomAccessReadView already closed"``
* ``RandomAccessReadBufferedFile.length()`` does NOT check closed: it returns
  the cached file length even after ``close()`` (upstream Java line 237).
* ``seek(past_end)`` clamps the position to ``length()`` and leaves the stream
  at EOF (subsequent ``read()`` returns ``-1``) for buffer and buffered-file.

These pins are literal-valued so they pass WITHOUT the oracle; a separate
``@requires_oracle`` differential test cross-checks against live PDFBox.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.random_access_read_buffered_file import RandomAccessReadBufferedFile
from pypdfbox.io.random_access_read_view import RandomAccessReadView
from pypdfbox.io.sequence_random_access_read import SequenceRandomAccessRead
from tests.oracle.harness import requires_oracle, run_probe_text


def _tmp(data: bytes) -> Path:
    fd, name = tempfile.mkstemp(suffix=".bin")
    p = Path(name)
    import os

    os.write(fd, data)
    os.close(fd)
    return p


# ---------------------------------------------------------------------------
# Negative seek -> OSError("Invalid position -1") for every class.
# ---------------------------------------------------------------------------


def test_buffer_negative_seek_message() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    with pytest.raises(OSError, match=r"Invalid position -1"):
        rar.seek(-1)


def test_buffered_file_negative_seek_message() -> None:
    p = _tmp(b"abc")
    try:
        r = RandomAccessReadBufferedFile(p)
        try:
            with pytest.raises(OSError, match=r"Invalid position -1"):
                r.seek(-1)
        finally:
            r.close()
    finally:
        p.unlink()


def test_sequence_negative_seek_message() -> None:
    seq = SequenceRandomAccessRead(
        [RandomAccessReadBuffer(b"abc"), RandomAccessReadBuffer(b"de")]
    )
    with pytest.raises(OSError, match=r"Invalid position -1"):
        seq.seek(-1)


def test_view_negative_seek_message() -> None:
    view = RandomAccessReadView(RandomAccessReadBuffer(b"abcdefgh"), 2, 4)
    with pytest.raises(OSError, match=r"Invalid position -1"):
        view.seek(-1)


# ---------------------------------------------------------------------------
# Operations after close() -> OSError with the upstream "already closed" text.
# ---------------------------------------------------------------------------


def test_buffer_closed_ops_raise_oserror() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    rar.close()
    msg = "RandomAccessBuffer already closed"
    for op in (rar.read, lambda: rar.seek(0), rar.get_position, rar.length):
        with pytest.raises(OSError, match=msg):
            op()


def test_buffered_file_closed_ops_raise_oserror() -> None:
    p = _tmp(b"abc")
    try:
        r = RandomAccessReadBufferedFile(p)
        r.close()
        msg = "org.apache.pdfbox.io.RandomAccessReadBufferedFile already closed"
        for op in (r.read, lambda: r.seek(0), r.get_position):
            with pytest.raises(OSError) as exc:
                op()
            assert str(exc.value) == msg
    finally:
        p.unlink()


def test_buffered_file_length_does_not_check_closed() -> None:
    # Upstream length() returns the cached file length even after close().
    p = _tmp(b"abcde")
    try:
        r = RandomAccessReadBufferedFile(p)
        assert r.length() == 5
        r.close()
        assert r.length() == 5  # no raise post-close
    finally:
        p.unlink()


def test_sequence_closed_ops_raise_oserror() -> None:
    seq = SequenceRandomAccessRead(
        [RandomAccessReadBuffer(b"abc"), RandomAccessReadBuffer(b"de")]
    )
    seq.close()
    msg = "RandomAccessBuffer already closed"
    for op in (seq.read, lambda: seq.seek(0), seq.get_position, seq.length):
        with pytest.raises(OSError, match=msg):
            op()


def test_view_closed_ops_raise_oserror() -> None:
    view = RandomAccessReadView(RandomAccessReadBuffer(b"abcdefgh"), 2, 4)
    view.close()
    msg = "RandomAccessReadView already closed"
    for op in (view.read, lambda: view.seek(0), view.get_position, view.length):
        with pytest.raises(OSError, match=msg):
            op()


# ---------------------------------------------------------------------------
# seek past end clamps + EOF read returns -1 (buffer + buffered-file).
# ---------------------------------------------------------------------------


def test_buffer_seek_past_end_clamps_and_reads_eof() -> None:
    rar = RandomAccessReadBuffer(b"abc")
    rar.seek(100)
    assert rar.get_position() == 3
    assert rar.is_eof() is True
    assert rar.read() == RandomAccessReadBuffer.EOF


def test_buffered_file_seek_past_end_clamps_and_reads_eof() -> None:
    p = _tmp(b"abc")
    try:
        r = RandomAccessReadBufferedFile(p)
        try:
            r.seek(100)
            assert r.get_position() == 3
            assert r.is_eof() is True
            assert r.read() == RandomAccessReadBufferedFile.EOF
        finally:
            r.close()
    finally:
        p.unlink()


# ---------------------------------------------------------------------------
# Differential cross-check against live PDFBox.
# ---------------------------------------------------------------------------


@requires_oracle
def test_oracle_matches_closed_and_seek_semantics() -> None:
    out = run_probe_text("RandomAccessReadSemanticsProbe")
    lines = dict(line.split("=", 1) for line in out.strip().splitlines())

    # Negative seek messages.
    assert lines["buf.seekNeg"] == "java.io.IOException|Invalid position -1"
    assert lines["file.seekNeg"] == "java.io.IOException|Invalid position -1"
    assert lines["seq.seekNeg"] == "java.io.IOException|Invalid position -1"
    assert lines["view.seekNeg"] == "java.io.IOException|Invalid position -1"

    # Closed-operation messages.
    assert (
        lines["buf.readClosed"]
        == "java.io.IOException|RandomAccessBuffer already closed"
    )
    assert (
        lines["file.readClosed"]
        == "java.io.IOException|org.apache.pdfbox.io."
        "RandomAccessReadBufferedFile already closed"
    )
    assert (
        lines["seq.readClosed"]
        == "java.io.IOException|RandomAccessBuffer already closed"
    )
    assert (
        lines["view.readClosed"]
        == "java.io.IOException|RandomAccessReadView already closed"
    )

    # length() on a closed buffered file does NOT throw.
    assert lines["file.lengthClosed"] == "NO_THROW"

    # seek-past-end clamps + EOF read.
    assert lines["buf.seekPastEnd.pos"] == "3"
    assert lines["buf.seekPastEnd.isEOF"] == "true"
    assert lines["buf.seekPastEnd.read"] == "-1"
    assert lines["file.seekPastEnd.pos"] == "3"
    assert lines["file.seekPastEnd.isEOF"] == "true"
    assert lines["file.seekPastEnd.read"] == "-1"

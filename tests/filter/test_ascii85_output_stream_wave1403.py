"""``ASCII85OutputStream`` flush/framing behaviour.

Wave 1463 rewrote the encoder as a faithful byte-for-byte port of upstream
``org.apache.pdfbox.filter.ASCII85OutputStream`` (running line-break counter,
group buffering, empty-input suppression) — replacing the earlier
``base64.a85encode``-based shim. These tests pin the observable flush output:
single-byte framing, the always-present trailing newline after ``~>``, the
hard line break every 72 output columns, and the empty-input suppression.
"""

from __future__ import annotations

import io

from pypdfbox.filter.ascii85_output_stream import ASCII85OutputStream


def test_flush_single_byte_frames_digits_marker_and_newline() -> None:
    """A 1-byte input flushes to its 2 base-85 digits, the ``~>`` EOD marker,
    and the trailing LF upstream always appends after ``>``."""
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.write(b"A")
    stream.flush()
    assert sink.getvalue() == b"5l~>\n"


def test_flush_is_idempotent_when_nothing_written() -> None:
    """An untouched stream emits NOTHING on flush (``flushed`` starts True) —
    not even the ``~>`` marker. Matches upstream for empty input."""
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.flush()
    assert sink.getvalue() == b""


def test_flush_folds_hard_line_break_every_72_columns() -> None:
    """Output longer than the 72-column line length carries hard ``\\n`` line
    breaks; the running counter spans full groups and the trailing group."""
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    # 100 non-zero bytes → 125 base-85 digits → one fold at column 72.
    stream.write(bytes((i % 250) + 1 for i in range(100)))
    stream.flush()
    out = sink.getvalue()
    # First newline lands right after the 72nd output digit.
    assert out.index(b"\n") == 72
    assert out.endswith(b"~>\n")


def test_detach_prevents_close_from_closing_underlying() -> None:
    """``detach`` swaps the destination so the wrapper's finaliser can't close
    a live caller buffer the encode chain still needs to read."""
    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.write(b"A")
    stream.flush()
    stream.detach()
    stream.close()
    assert not sink.closed
    assert sink.getvalue() == b"5l~>\n"

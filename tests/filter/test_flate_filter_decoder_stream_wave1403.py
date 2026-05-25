"""Wave 1403 branch round-out for ``FlateFilterDecoderStream.read``.

Closes 101->106 — the ``while not self._eof`` loop in the unbounded
(``size < 0``) read path exits via its *condition* (rather than the inner
``break``). The existing read-all tests always exhaust the stream from the
start and leave the loop through ``if not self.fetch(): break`` (line 103),
so the while-condition-False exit (101->106) was never taken.

To reach 101->106 the loop must re-check ``while not self._eof`` after the
body has run with ``_eof`` already True. That state is exactly "EOF reached
but the decode buffer still holds undelivered bytes": ``read(-1)`` then
drains the buffered remainder and the very first while-check is False.
"""

from __future__ import annotations

import io
import zlib

from pypdfbox.filter import FlateFilterDecoderStream


def test_read_all_with_eof_set_and_buffered_tail_exits_via_condition() -> None:
    """Closes 101->106: with ``_eof`` already True and bytes still buffered,
    ``read(-1)`` drains the buffer and the ``while not self._eof`` check is
    False on entry, jumping straight to the return."""
    raw = b"hello flate world"
    compressed = zlib.compress(raw)
    stream = FlateFilterDecoderStream(io.BytesIO(compressed))

    # Materialise a buffered remainder, then mark EOF — the precise state the
    # loop's condition-exit handles (decoder is done but data is still queued).
    first = stream.read(4)
    assert first == raw[:4]
    assert len(stream._buffer) > stream._buffer_pos  # noqa: SLF001 — bytes remain
    stream._eof = True  # noqa: SLF001 — decoder exhausted, buffer not drained

    rest = stream.read(-1)
    # The buffered remainder is returned; no further fetch was attempted.
    assert first + rest == raw[: len(first) + len(rest)]
    assert rest == raw[4:]

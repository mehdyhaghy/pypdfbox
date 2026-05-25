"""Wave 1403 branch round-out for ``RandomAccessReadView.read_into``.

Closes 122->124 — the ``if read_bytes > 0`` False arm: when the view's
declared ``stream_length`` extends past the parent's real data, the view's
``available()`` reports bytes that do not exist; the parent's ``read_into``
then returns 0 and the position-advance is skipped.
"""

from __future__ import annotations

from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.random_access_read_view import RandomAccessReadView


def test_read_into_returns_zero_when_parent_has_no_bytes() -> None:
    """Closes 122->124: the view starts at the parent's EOF but claims a
    longer logical length, so ``available()`` > 0 while the parent yields 0
    bytes — ``read_bytes > 0`` is False and the cursor does not advance.
    """
    parent = RandomAccessReadBuffer(b"abc")  # only 3 bytes
    # Window begins *at* the parent's EOF, but claims 10 logical bytes.
    view = RandomAccessReadView(parent, start_position=3, stream_length=10)

    assert view.is_eof() is False  # current_position(0) < stream_length(10)
    assert view.available() == 10

    buf = bytearray(10)
    read_bytes = view.read_into(buf, 0, 10)
    # Parent had nothing at position 3 => 0 bytes copied, position unchanged.
    assert read_bytes <= 0
    assert view.get_position() == 0

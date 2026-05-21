"""Wave 1345: residual coverage for ``RandomAccessReadUnbufferedDataStream``.

Targets:
  - signed-long round-trip via ``read_long`` (top-bit set yields a
    negative result through ``read_int``'s sign extension);
  - the early-EOF break inside ``get_original_data``;
  - the ``get_original_input_stream`` convenience helper;
  - the ``OSError → None`` fallback inside ``create_sub_view``.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.random_access_read_non_closing_input_stream import (
    RandomAccessReadNonClosingInputStream,
)
from pypdfbox.fontbox.ttf.random_access_read_unbuffered_data_stream import (
    RandomAccessReadUnbufferedDataStream,
)
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer


def test_read_long_sign_extends_high_bit() -> None:
    """A combined 64-bit value with the top bit set yields a negative int.

    ``read_int`` returns a signed Python int, so ``high`` is already
    negative for upper-half values; the bit-or with the unsigned ``low``
    produces the correct signed 64-bit value.
    """
    # 0x8000000000000000 -> -2**63 after sign extension.
    buf = RandomAccessReadBuffer(b"\x80\x00\x00\x00\x00\x00\x00\x00")
    s = RandomAccessReadUnbufferedDataStream(buf)
    assert s.read_long() == -(2**63)


def test_read_long_round_trip_for_negative_value() -> None:
    """Round-trip a known signed 64-bit value through ``read_long`` to
    confirm sign extension is preserved across a non-trivial bit
    pattern."""
    # 0xFFFFFFFFFFFFFFFE -> -2.
    buf = RandomAccessReadBuffer(b"\xff\xff\xff\xff\xff\xff\xff\xfe")
    s = RandomAccessReadUnbufferedDataStream(buf)
    assert s.read_long() == -2


def test_get_original_data_handles_short_read() -> None:
    """When the backing view returns -1 (EOF) before ``length`` bytes have
    been collected, ``get_original_data`` breaks out and returns the
    bytes accumulated so far (line 137-138)."""

    class _ShortReadOnceBuffer(RandomAccessReadBuffer):
        def create_view(self, position: int, length: int):  # type: ignore[override]
            inner_view = super().create_view(position, length)

            class _ShortView:
                """Mimics RandomAccessRead but returns -1 after the first read."""

                def __init__(self, v: object) -> None:
                    self._v = v
                    self._first = True

                def read_into(self, buf: bytearray, offset: int, length: int) -> int:
                    if not self._first:
                        return -1
                    self._first = False
                    # Read only half the requested bytes, then bail.
                    return self._v.read_into(buf, offset, min(2, length))

                def close(self) -> None:
                    self._v.close()

            return _ShortView(inner_view)

    payload = b"abcdefgh"
    buf = _ShortReadOnceBuffer(payload)
    s = RandomAccessReadUnbufferedDataStream(buf)
    data = s.get_original_data()
    # We get back only the first chunk before the view-shaped helper
    # returned -1 and broke the loop.
    assert data == b"ab"


def test_get_original_input_stream_returns_non_closing_view() -> None:
    """The streaming helper wraps the inner view in a non-closing input."""
    payload = b"hello world"
    buf = RandomAccessReadBuffer(payload)
    s = RandomAccessReadUnbufferedDataStream(buf)
    stream = s.get_original_input_stream()
    assert isinstance(stream, RandomAccessReadNonClosingInputStream)
    # The stream reads the entire backing payload.
    assert stream.read() == payload


def test_create_sub_view_returns_none_on_create_view_oserror() -> None:
    """If the backing read raises ``OSError`` during ``create_view``,
    ``create_sub_view`` returns ``None`` rather than propagating
    (mirrors upstream's defensive try/catch)."""

    class _ExplodingBuffer(RandomAccessReadBuffer):
        def __init__(self, payload: bytes) -> None:
            super().__init__(payload)
            self._initialised = True

        def create_view(self, position: int, length: int):  # type: ignore[override]
            # Allow the constructor-side ``length()`` call to succeed; raise
            # only when the test explicitly asks for a sub-view (i.e. after
            # the stream is fully constructed).
            if getattr(self, "_initialised", False) and position > 0:
                raise OSError("simulated failure")
            return super().create_view(position, length)

    buf = _ExplodingBuffer(b"abcdef")
    s = RandomAccessReadUnbufferedDataStream(buf)
    s.seek(2)
    assert s.create_sub_view(3) is None

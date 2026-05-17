"""Wave 1345: residual coverage for ``RandomAccessReadUnbufferedDataStream``.

Targets:
  - the signed-64-bit sign-extension branch of ``read_long`` (line 84);
  - the early-EOF break inside ``get_original_data`` (line 138);
  - the ``get_original_input_stream`` convenience helper (line 152);
  - the ``OSError → None`` fallback inside ``create_sub_view``
    (lines 175-176).
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

    The branch at line 83-84 subtracts ``2**64`` when ``combined`` is
    above the signed-64-bit positive range.
    """
    # 0x8000000000000000 -> -2**63 after sign extension.
    buf = RandomAccessReadBuffer(b"\x80\x00\x00\x00\x00\x00\x00\x00")
    s = RandomAccessReadUnbufferedDataStream(buf)
    assert s.read_long() == -(2**63)


def test_read_long_via_explicit_unsigned_high_word() -> None:
    """Force the defensive sign-extension branch by feeding an unsigned
    high-word into ``read_long`` directly.

    Upstream's ``read_int`` already sign-extends, so the conditional at
    line 83 (``combined >= 0x8000_0000_0000_0000``) is normally dead.
    We patch ``read_int`` to return the *unsigned* form (high-bit value as
    a positive int) which Java's ``int`` cast would also lose; this
    re-engages the explicit clamp.
    """
    buf = RandomAccessReadBuffer(b"\x00" * 8)
    s = RandomAccessReadUnbufferedDataStream(buf)
    # First call returns 0x80000000 as an UNSIGNED positive int; second
    # returns 0. This produces combined = 0x80000000_00000000 which trips
    # the defensive clamp.
    values = iter([0x80000000, 0])
    s.read_int = lambda: next(values)  # type: ignore[method-assign]
    assert s.read_long() == -(2**63)


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

from __future__ import annotations

from typing import TYPE_CHECKING

from .random_access_read_non_closing_input_stream import (
    RandomAccessReadNonClosingInputStream,
)
from .ttf_data_stream import TTFDataStream

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead


class RandomAccessReadUnbufferedDataStream(TTFDataStream):
    """Unbuffered :class:`TTFDataStream` over a :class:`RandomAccessRead`.

    Mirrors ``org.apache.fontbox.ttf.RandomAccessReadUnbufferedDataStream``
    (``RandomAccessReadUnbufferedDataStream.java`` lines 31-145).

    In contrast to :class:`RandomAccessReadDataStream`, this class does
    not pre-load the entire :class:`RandomAccessRead` into a ``bytes``
    buffer — it works against the random-access read directly. This is
    much faster when most of the source is skipped (e.g. parsing only
    the table directories of a TTC) and slower when the whole stream
    is read.

    The class is package-private upstream (``class`` with no
    ``public``); we expose it as a public module since Python lacks
    enforced access control and parity tooling needs to reach the
    class by name.
    """

    def __init__(self, random_access_read: RandomAccessRead) -> None:
        """Wrap ``random_access_read``.

        Mirrors ``RandomAccessReadUnbufferedDataStream(RandomAccessRead)``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 39-43). The
        length is captured up-front (upstream calls
        ``randomAccessRead.length()`` once and stores the result) so
        :meth:`get_original_data_size` is O(1) regardless of the
        backing implementation.
        """
        self._length: int = random_access_read.length()
        self._random_access_read: RandomAccessRead = random_access_read

    # ---- abstract overrides ----

    def get_current_position(self) -> int:
        """Mirror ``long getCurrentPosition()``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 48-52)."""
        return self._random_access_read.get_position()

    def close(self) -> None:
        """Close the underlying :class:`RandomAccessRead`.

        Mirrors ``void close()`` (``RandomAccessReadUnbufferedDataStream.java``
        lines 59-63). In contrast to :class:`TTCDataStream` (whose
        close is a no-op so the shared stream survives), this class
        owns the underlying read and closes it.
        """
        self._random_access_read.close()

    def read(self) -> int:
        """Mirror ``int read()``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 69-72)."""
        return self._random_access_read.read()

    def read_long(self) -> int:
        """Mirror ``long readLong()``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 78-81).

        Upstream computes ``((long) readInt() << 32) | (readInt() &
        0xFFFFFFFFL)`` — two big-endian ints combined into a signed
        64-bit long. We mirror that path so EOF semantics match (read
        through silently like Java's ``readInt``).

        :meth:`read_int` already sign-extends its return to a signed
        32-bit Python int, so ``high`` is already negative for
        upper-half values; bit-or with the unsigned ``low`` therefore
        produces the correct signed 64-bit value with no extra clamp.
        """
        high = self.read_int()
        low = self.read_int() & 0xFFFF_FFFF
        return (high << 32) | low

    def read_int(self) -> int:
        """Read a signed 32-bit big-endian integer.

        Mirrors the private ``int readInt()``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 86-93). Java's
        ``read()`` returns -1 at EOF and propagates through the
        shift / mask without raising; we mirror that behaviour rather
        than raising ``EOFError`` so callers see the same bit pattern.
        """
        b1 = self.read()
        b2 = self.read()
        b3 = self.read()
        b4 = self.read()
        v = (
            ((b1 & 0xFF) << 24)
            | ((b2 & 0xFF) << 16)
            | ((b3 & 0xFF) << 8)
            | (b4 & 0xFF)
        )
        if v >= 0x8000_0000:
            v -= 0x1_0000_0000
        return v

    def seek(self, pos: int) -> None:
        """Mirror ``void seek(long pos)``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 98-102)."""
        self._random_access_read.seek(pos)

    def read_into(self, buf: bytearray, offset: int, length: int) -> int:
        """Mirror ``int read(byte[] b, int off, int len)``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 107-111)."""
        return self._random_access_read.read_into(buf, offset, length)

    def get_original_data(self) -> bytes:
        """Return the entire underlying byte stream.

        Upstream returns a non-closing ``InputStream`` view
        (``RandomAccessReadUnbufferedDataStream.java`` lines 118-122).
        Our :class:`TTFDataStream` contract demands ``bytes``, so we
        materialise the view here. Callers that need the streaming
        ``InputStream``-shaped behaviour can construct a
        :class:`RandomAccessReadNonClosingInputStream` directly from
        the backing :class:`RandomAccessRead` instead.
        """
        view = self._random_access_read.create_view(0, self._length)
        try:
            buf = bytearray(self._length)
            total = 0
            while total < self._length:
                n = view.read_into(buf, total, self._length - total)
                if n <= 0:
                    break
                total += n
            return bytes(buf[:total])
        finally:
            view.close()

    def get_original_input_stream(self) -> RandomAccessReadNonClosingInputStream:
        """Streaming variant of :meth:`get_original_data`.

        Convenience that mirrors upstream's actual ``getOriginalData``
        return type — a non-closing ``InputStream`` view over the full
        random-access read. Callers can iterate the stream without
        loading every byte into memory.
        """
        return RandomAccessReadNonClosingInputStream(
            self._random_access_read.create_view(0, self._length),
        )

    def get_original_data_size(self) -> int:
        """Mirror ``long getOriginalDataSize()``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 127-131)."""
        return self._length

    def create_sub_view(self, length: int) -> RandomAccessRead | None:
        """Mirror ``RandomAccessRead createSubView(long length)``
        (``RandomAccessReadUnbufferedDataStream.java`` lines 133-145).

        Upstream catches ``IOException`` from ``createView`` and
        returns ``null`` after an ``assert false``. We mirror that
        defensive shape and return ``None`` if the underlying read
        cannot produce a view.
        """
        try:
            return self._random_access_read.create_view(
                self._random_access_read.get_position(),
                length,
            )
        except OSError:
            return None


__all__ = ["RandomAccessReadUnbufferedDataStream"]

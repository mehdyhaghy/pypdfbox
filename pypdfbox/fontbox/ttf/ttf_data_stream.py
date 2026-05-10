from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

from pypdfbox.io.random_access_read import RandomAccessRead

_LOG = logging.getLogger(__name__)

# Epoch for TrueType `LONGDATETIME`: midnight 1904-01-01 UTC. Stored as a
# signed 64-bit count of seconds. Naïve datetimes break around year-2038, so
# we use ``datetime`` + ``timedelta(seconds=...)`` to stay safe.
_TTF_EPOCH: datetime = datetime(1904, 1, 1, 0, 0, 0, tzinfo=UTC)


class TTFDataStream(ABC):
    """
    Abstract reader for the binary TrueType wire format.

    Mirrors ``org.apache.fontbox.ttf.TTFDataStream``. Concrete subclasses are
    :class:`RandomAccessReadDataStream` (lazy random-access; supports `seek`)
    and :class:`MemoryTTFDataStream` (one-shot in-memory; mostly used for
    embedded fonts already pre-loaded into a ``bytes``).
    """

    @abstractmethod
    def read(self) -> int:
        """Read one unsigned byte. Returns 0..255 or -1 at EOF."""

    @abstractmethod
    def read_long(self) -> int:
        """Read a signed 64-bit big-endian integer."""

    @abstractmethod
    def read_into(self, buf: bytearray, offset: int, length: int) -> int:
        """Read up to ``length`` bytes into ``buf`` at ``offset``.

        Returns the number of bytes actually read, or -1 if EOF reached
        before any byte was read. Mirrors Java
        ``InputStream.read(byte[], int, int)``.
        """

    @abstractmethod
    def seek(self, pos: int) -> None:
        """Seek to absolute byte offset ``pos``."""

    @abstractmethod
    def get_current_position(self) -> int:
        """Current byte offset."""

    @abstractmethod
    def get_original_data(self) -> bytes:
        """Return the entire underlying byte stream as bytes."""

    @abstractmethod
    def get_original_data_size(self) -> int:
        """Size of the underlying byte stream."""

    @abstractmethod
    def close(self) -> None:
        """Release underlying resources."""

    @staticmethod
    def _read_capacity(buf: bytearray, offset: int, length: int) -> int:
        if offset < 0 or offset > len(buf) or length < 0:
            msg = (
                f"read_into range out of bounds: offset={offset}, "
                f"length={length}, buffer length={len(buf)}"
            )
            raise IndexError(msg)
        return len(buf) - offset

    @staticmethod
    def _check_read_bounds(buf: bytearray, offset: int, length: int) -> None:
        capacity = TTFDataStream._read_capacity(buf, offset, length)
        if length > capacity:
            msg = (
                f"read_into range out of bounds: offset={offset}, "
                f"length={length}, buffer length={len(buf)}"
            )
            raise IndexError(msg)

    @staticmethod
    def _checked_read_count(
        buf: bytearray, offset: int, length: int, available: int
    ) -> int:
        capacity = TTFDataStream._read_capacity(buf, offset, length)
        if length == 0:
            return 0
        if available <= 0:
            return -1
        n = min(length, available)
        if n > capacity:
            msg = (
                f"read_into range out of bounds: offset={offset}, "
                f"length={length}, buffer length={len(buf)}"
            )
            raise IndexError(msg)
        return n

    # ---- helpers (translated 1:1 from upstream TTFDataStream) ----

    def read_signed_byte(self) -> int:
        b = self.read()
        if b == -1:
            raise EOFError("premature EOF reading signed byte")
        return b if b <= 127 else b - 256

    def read_unsigned_byte(self) -> int:
        b = self.read()
        if b == -1:
            raise EOFError("premature EOF reading unsigned byte")
        return b

    def read_unsigned_short(self) -> int:
        b1 = self.read()
        b2 = self.read()
        if b1 < 0 or b2 < 0:
            raise EOFError(
                f"EOF at {self.get_current_position()}, b1: {b1}, b2: {b2}"
            )
        return (b1 << 8) | b2

    def read_signed_short(self) -> int:
        v = self.read_unsigned_short()
        return v - 0x10000 if v >= 0x8000 else v

    def read_unsigned_int(self) -> int:
        """Read a 32-bit unsigned big-endian integer (returned as a Python int)."""
        b1 = self.read()
        b2 = self.read()
        b3 = self.read()
        b4 = self.read()
        if b1 < 0 or b2 < 0 or b3 < 0 or b4 < 0:
            raise EOFError(
                f"EOF at {self.get_current_position()}, "
                f"b1: {b1}, b2: {b2}, b3: {b3}, b4: {b4}"
            )
        return (b1 << 24) | (b2 << 16) | (b3 << 8) | b4

    def read_32_fixed(self) -> float:
        """Read a 16.16 fixed-point value as a float."""
        whole = self.read_signed_short()
        frac = self.read_unsigned_short()
        return whole + frac / 65536.0

    def read_tag(self) -> str:
        """Read a 4-byte ASCII tag."""
        return self._read(4).decode("ascii")

    # convenience: bulk read of N bytes (raises if short)
    def _read(self, n: int) -> bytes:
        data = bytearray(n)
        total = 0
        while total < n:
            got = self.read_into(data, total, n - total)
            if got <= 0:
                break
            total += got
        if total != n:
            raise OSError("Unexpected end of TTF stream reached")
        return bytes(data)

    def read_bytes(self, n: int) -> bytes:
        """Read exactly n bytes; raises ``OSError`` on short read."""
        return self._read(n)

    def read_string(self, length: int, encoding: str = "iso-8859-1") -> str:
        """Read a fixed-length string in the given encoding (default ISO-8859-1)."""
        return self._read(length).decode(encoding)

    def read_unsigned_byte_array(self, length: int) -> list[int]:
        return list(self._read(length))

    def read_unsigned_short_array(self, length: int) -> list[int]:
        out = [0] * length
        for i in range(length):
            out[i] = self.read_unsigned_short()
        return out

    def read_long_date_time(self) -> datetime:
        """Read an OpenType ``LONGDATETIME`` (signed 64-bit seconds since 1904-01-01 UTC)."""
        seconds_since_1904 = self.read_long()
        return _TTF_EPOCH + timedelta(seconds=seconds_since_1904)

    def read_international_date(self) -> datetime:
        """Read an eight-byte international date (signed 64-bit seconds since 1904-01-01 UTC).

        Mirrors upstream ``TTFDataStream.readInternationalDate``.
        """
        return self.read_long_date_time()

    def create_sub_view(self, length: int) -> RandomAccessRead | None:
        """
        Return a ``RandomAccessRead`` view spanning the next ``length`` bytes
        from the current position, or ``None`` when this stream cannot
        produce a view (caller should fall back to :meth:`read_bytes`).

        Mirrors upstream ``TTFDataStream.createSubView``: subclasses with a
        random-access backing store override; the abstract default returns
        ``None``. Closing the returned view must not affect this stream.
        """
        return None


class RandomAccessReadDataStream(TTFDataStream):
    """Wraps a :class:`RandomAccessRead` to satisfy :class:`TTFDataStream`.

    Mirrors upstream ``RandomAccessReadDataStream``: pulls the entire
    underlying stream into memory once (TTF directories require many seeks)
    so subsequent reads/seeks are O(1).
    """

    def __init__(self, source: RandomAccessRead | BinaryIO | bytes | bytearray) -> None:
        # Mirrors upstream's two constructors: ``RandomAccessReadDataStream(RandomAccessRead)``
        # slurps the whole source via ``length()`` + ``read(...)``; the input-stream
        # overload (``RandomAccessReadDataStream(InputStream)``) drains the stream via
        # ``IOUtils.toByteArray``. Dispatch is duck-typed: anything exposing
        # ``length()`` + ``read_into(...)`` looks like RandomAccessRead;
        # otherwise we treat ``source`` as a file-like / input stream.
        if isinstance(source, (bytes, bytearray)):
            self._data: bytes = bytes(source)
        elif hasattr(source, "length") and hasattr(source, "read_into"):
            size = source.length()
            buf = bytearray(size)
            source.seek(0)
            # read in a loop in case the source returns short reads
            total = 0
            while total < size:
                n = source.read_into(buf, total, size - total)
                if n <= 0:
                    break
                total += n
            if total != size:
                raise OSError("Unexpected end of TTF stream reached")
            self._data = bytes(buf)
        else:
            # File-like / InputStream: drain to EOF.
            data = source.read()
            if not isinstance(data, (bytes, bytearray)):
                msg = "input stream must return bytes from read()"
                raise TypeError(msg)
            self._data = bytes(data)
        self._pos: int = 0
        self._closed = False

    # ---- core ----
    def read(self) -> int:
        if self._pos >= len(self._data):
            return -1
        b = self._data[self._pos]
        self._pos += 1
        return b

    def read_long(self) -> int:
        if self._pos + 8 > len(self._data):
            raise EOFError("premature EOF reading long")
        v = int.from_bytes(self._data[self._pos : self._pos + 8], "big", signed=True)
        self._pos += 8
        return v

    def read_into(self, buf: bytearray, offset: int, length: int) -> int:
        avail = len(self._data) - self._pos
        n = self._checked_read_count(buf, offset, length, avail)
        if n <= 0:
            return n
        buf[offset : offset + n] = self._data[self._pos : self._pos + n]
        self._pos += n
        return n

    def seek(self, pos: int) -> None:
        if pos < 0:
            raise OSError(f"seek to negative position {pos}")
        # upstream seeks past EOF are tolerated; reads then fail naturally.
        self._pos = pos

    def get_current_position(self) -> int:
        return self._pos

    def get_original_data(self) -> bytes:
        return self._data

    def get_original_data_size(self) -> int:
        return len(self._data)

    def close(self) -> None:
        self._closed = True

    def create_sub_view(self, length: int) -> RandomAccessRead | None:
        """Return a sliced view starting at the current position.

        Mirrors upstream ``RandomAccessReadDataStream.createSubView``: build
        a fresh ``RandomAccessReadBuffer`` over our cached bytes and return
        a ``createView`` of ``length`` bytes from the cursor. Closing the
        returned view does not affect this stream (the new buffer owns it).
        Returns ``None`` if the underlying buffer cannot produce a view.
        """
        # Local import to avoid an import cycle (io -> fontbox -> io).
        from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

        try:
            buffer = RandomAccessReadBuffer(self._data)
            return buffer.create_view(self._pos, length)
        except Exception:  # pragma: no cover — defensive: log + None like upstream
            _LOG.warning("Could not create a SubView", exc_info=True)
            return None


class MemoryTTFDataStream(TTFDataStream):
    """In-memory variant constructed directly from ``bytes``.

    Mirrors upstream ``MemoryTTFDataStream``. Used by ``GlyphTable`` to wrap
    the slice of bytes for the ``glyf`` table so the underlying file handle
    can be released early.
    """

    def __init__(self, data: bytes | bytearray) -> None:
        self._data = bytes(data)
        self._pos = 0
        self._closed = False

    def read(self) -> int:
        if self._pos >= len(self._data):
            return -1
        b = self._data[self._pos]
        self._pos += 1
        return b

    def read_long(self) -> int:
        if self._pos + 8 > len(self._data):
            raise EOFError("premature EOF reading long")
        v = int.from_bytes(self._data[self._pos : self._pos + 8], "big", signed=True)
        self._pos += 8
        return v

    def read_into(self, buf: bytearray, offset: int, length: int) -> int:
        avail = len(self._data) - self._pos
        n = self._checked_read_count(buf, offset, length, avail)
        if n <= 0:
            return n
        buf[offset : offset + n] = self._data[self._pos : self._pos + n]
        self._pos += n
        return n

    def seek(self, pos: int) -> None:
        if pos < 0:
            raise OSError(f"seek to negative position {pos}")
        self._pos = pos

    def get_current_position(self) -> int:
        return self._pos

    def get_original_data(self) -> bytes:
        return self._data

    def get_original_data_size(self) -> int:
        return len(self._data)

    def close(self) -> None:
        self._closed = True

    def create_sub_view(self, length: int) -> RandomAccessRead | None:
        """Return a ``RandomAccessRead`` view over the next ``length`` bytes.

        Same contract as :meth:`RandomAccessReadDataStream.create_sub_view`
        but for the in-memory variant; closing the returned view does not
        affect this stream.
        """
        from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

        try:
            buffer = RandomAccessReadBuffer(self._data)
            return buffer.create_view(self._pos, length)
        except Exception:  # pragma: no cover
            _LOG.warning("Could not create a SubView", exc_info=True)
            return None

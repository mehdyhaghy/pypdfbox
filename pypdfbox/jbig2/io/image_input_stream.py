from __future__ import annotations

import struct
from typing import BinaryIO

# End-of-stream sentinel returned by the byte-level ``read`` methods, mirroring
# the ``-1`` that ``java.io.InputStream.read()`` / ``ImageInputStream.read()``
# return at end of stream.
EOF: int = -1


class ImageInputStream:
    """
    A big-endian, seekable, bit-addressable input stream.

    Mirrors the slice of ``javax.imageio.stream.ImageInputStream`` /
    ``ImageInputStreamImpl`` that the JBIG2 decoder relies on. The JBIG2 reader
    consumes its input through this surface: ``read_bit`` / ``read_bits`` for the
    arithmetic and header bit fields, ``read_byte`` for AT pixel offsets,
    ``read_unsigned_int`` for the page count, plus ``seek`` / ``mark`` /
    ``reset`` / ``align`` for positioning.

    Bit order is **big-endian within each byte**: ``read_bit`` returns bit 7
    (the most significant bit) of the current byte first. ``read_bits(n)``
    accumulates ``n`` bits most-significant-first across byte boundaries and
    returns them as an unsigned integer. This matches Java's
    ``ImageInputStreamImpl`` exactly.

    The base implementation is backed by an in-memory ``bytes`` buffer, which is
    the model the upstream ``MemoryCacheImageInputStream`` provides and is what
    the PDF ``/JBIG2Decode`` filter feeds (the stream payload is fully buffered
    before decoding). :class:`SubInputStream` wraps an instance of this class to
    expose a windowed view.

    State, mirroring ``ImageInputStreamImpl``:

    * ``stream_pos`` — byte position of the next byte to read.
    * ``bit_offset`` — 0..7, the next bit within the current byte (0 == MSB).
    """

    def __init__(self, data: bytes | bytearray | memoryview | BinaryIO) -> None:
        if isinstance(data, (bytes, bytearray, memoryview)):
            self._data: bytes = bytes(data)
        else:
            # A binary file-like object: buffer it fully, matching the
            # MemoryCacheImageInputStream behaviour the decoder expects.
            self._data = data.read()
        self.stream_pos: int = 0
        self.bit_offset: int = 0
        self._closed: bool = False
        self._mark_stack: list[tuple[int, int]] = []

    # ------------------------------------------------------------------ #
    # Position / bit-offset accessors (ImageInputStreamImpl surface)
    # ------------------------------------------------------------------ #
    def get_stream_position(self) -> int:
        """Return the current byte position (``getStreamPosition``)."""
        self._check_closed()
        return self.stream_pos

    def get_bit_offset(self) -> int:
        """Return the current bit offset 0..7 (``getBitOffset``)."""
        self._check_closed()
        return self.bit_offset

    def set_bit_offset(self, bit_offset: int) -> None:
        """Set the current bit offset (``setBitOffset``); must be 0..7."""
        self._check_closed()
        if bit_offset < 0 or bit_offset > 7:
            raise ValueError(f"bitOffset must be between 0 and 7! (got {bit_offset})")
        self.bit_offset = bit_offset

    def seek(self, pos: int) -> None:
        """
        Seek to absolute byte position ``pos`` and reset the bit offset to 0.

        Mirrors ``ImageInputStreamImpl.seek(long)``: a seek always clears the
        pending bit offset.
        """
        self._check_closed()
        if pos < 0:
            raise OSError("pos < 0")
        self.stream_pos = pos
        self.bit_offset = 0

    def length(self) -> int:
        """Return the total length in bytes, or -1 if unknown (``length``)."""
        return len(self._data)

    # ------------------------------------------------------------------ #
    # Byte-level reads
    # ------------------------------------------------------------------ #
    def read(self) -> int:
        """
        Read one unsigned byte (0..255), or :data:`EOF` (-1) at end of stream.

        Mirrors ``ImageInputStreamImpl.read()``: resets ``bit_offset`` to 0
        before reading.
        """
        self._check_closed()
        self.bit_offset = 0
        if self.stream_pos >= len(self._data):
            return EOF
        value = self._data[self.stream_pos]
        self.stream_pos += 1
        return value

    def read_full(self, b: bytearray, off: int = 0, length: int | None = None) -> int:
        """
        Read up to ``length`` bytes into ``b`` starting at ``off``.

        Returns the number of bytes read, or :data:`EOF` (-1) at end of stream.
        Mirrors ``ImageInputStreamImpl.read(byte[], int, int)``: resets the bit
        offset to 0.
        """
        self._check_closed()
        if length is None:
            length = len(b) - off
        if off < 0 or length < 0 or off + length > len(b):
            raise IndexError("offset/length out of bounds")
        self.bit_offset = 0
        if self.stream_pos >= len(self._data):
            return EOF
        if length == 0:
            return 0
        to_read = min(length, len(self._data) - self.stream_pos)
        b[off : off + to_read] = self._data[self.stream_pos : self.stream_pos + to_read]
        self.stream_pos += to_read
        return to_read

    def read_byte(self) -> int:
        """
        Read one signed byte (-128..127). Mirrors ``readByte()``.

        Raises :class:`EOFError` at end of stream (Java ``EOFException``).
        """
        value = self.read()
        if value < 0:
            raise EOFError()
        return value - 256 if value >= 128 else value

    def read_unsigned_byte(self) -> int:
        """Read one unsigned byte (0..255). Mirrors ``readUnsignedByte()``."""
        value = self.read()
        if value < 0:
            raise EOFError()
        return value

    def read_unsigned_int(self) -> int:
        """
        Read a big-endian 32-bit unsigned integer (0..2**32-1).

        Mirrors ``readUnsignedInt()``; used for the page-count field.
        """
        buf = self._read_n_bytes(4)
        return struct.unpack(">I", buf)[0]

    def read_short(self) -> int:
        """Read a big-endian signed 16-bit integer. Mirrors ``readShort()``."""
        buf = self._read_n_bytes(2)
        return struct.unpack(">h", buf)[0]

    def read_unsigned_short(self) -> int:
        """Read a big-endian unsigned 16-bit integer. ``readUnsignedShort()``."""
        buf = self._read_n_bytes(2)
        return struct.unpack(">H", buf)[0]

    def read_int(self) -> int:
        """Read a big-endian signed 32-bit integer. Mirrors ``readInt()``."""
        buf = self._read_n_bytes(4)
        return struct.unpack(">i", buf)[0]

    def _read_n_bytes(self, n: int) -> bytes:
        """Read exactly ``n`` bytes (bit offset reset to 0) or raise EOFError."""
        buf = bytearray(n)
        self.read_fully(buf, 0, n)
        return bytes(buf)

    def read_fully(self, b: bytearray, off: int = 0, length: int | None = None) -> None:
        """
        Read exactly ``length`` bytes into ``b`` starting at ``off``.

        Mirrors ``ImageInputStreamImpl.readFully(byte[], int, int)``: loops over
        :meth:`read_full` and raises :class:`EOFError` if the stream ends first.
        """
        if length is None:
            length = len(b) - off
        if off < 0 or length < 0 or off + length > len(b):
            raise IndexError("offset/length out of bounds")
        while length > 0:
            nbytes = self.read_full(b, off, length)
            if nbytes == EOF:
                raise EOFError()
            off += nbytes
            length -= nbytes

    # ------------------------------------------------------------------ #
    # Bit-level reads (big-endian within each byte)
    # ------------------------------------------------------------------ #
    def read_bit(self) -> int:
        """
        Read a single bit (0 or 1). Mirrors ``ImageInputStreamImpl.readBit()``.

        Bits are consumed most-significant-first. Built on :meth:`read` /
        :meth:`seek` exactly like the JDK, so subclasses (notably
        :class:`SubInputStream`) only need to override the byte-level methods.

        Raises :class:`EOFError` at end of stream.
        """
        self._check_closed()
        # Compute final bit offset before we call read() and seek().
        new_bit_offset = (self.bit_offset + 1) & 0x7
        val = self.read()
        if val == EOF:
            raise EOFError()
        if new_bit_offset != 0:
            # Move byte position back if we are still in the middle of a byte.
            val >>= 8 - new_bit_offset
            self.seek(self.get_stream_position() - 1)
        self.bit_offset = new_bit_offset
        return val & 0x1

    def read_bits(self, num_bits: int) -> int:
        """
        Read ``num_bits`` (0..64) big-endian bits and return them as an integer.

        Mirrors ``ImageInputStreamImpl.readBits(int)`` verbatim: it reads whole
        bytes via :meth:`read_fully`, accumulates them big-endian, then shifts
        and masks down to ``num_bits`` and seeks back over any partial trailing
        byte. ``num_bits == 0`` returns 0 without moving the position. Building
        on :meth:`read_fully` / :meth:`seek` lets :class:`SubInputStream` reuse
        this unchanged.

        Raises :class:`EOFError` if the stream ends before ``num_bits`` are
        available.
        """
        self._check_closed()
        if num_bits < 0 or num_bits > 64:
            raise ValueError("num_bits must be between 0 and 64")
        if num_bits == 0:
            return 0

        # Have to read additional bits on the left equal to the bit offset.
        bits_to_read = num_bits + self.bit_offset
        bytes_to_read = (bits_to_read + 7) // 8
        bufferpos = self.get_stream_position()

        buf = bytearray(bytes_to_read)
        self.read_fully(buf, 0, bytes_to_read)

        accum = 0
        for byte in buf:
            accum = (accum << 8) | byte

        bits_at_bottom = (8 - (bits_to_read & 0x7)) & 0x7
        accum >>= bits_at_bottom
        accum &= (1 << num_bits) - 1

        newpos = bufferpos + (bits_to_read >> 3)
        self.seek(newpos)
        self.bit_offset = bits_to_read & 0x7
        return accum

    # ------------------------------------------------------------------ #
    # Alignment / mark / reset
    # ------------------------------------------------------------------ #
    def align(self) -> None:
        """
        Skip to the next byte boundary if the bit offset is non-zero.

        Mirrors the ``align()`` the MMR decompressor calls (the JDK clears the
        pending bits and advances to the next byte).
        """
        self._check_closed()
        if self.bit_offset != 0:
            self.bit_offset = 0
            self.stream_pos += 1

    def mark(self) -> None:
        """Push the current ``(stream_pos, bit_offset)`` onto the mark stack."""
        self._check_closed()
        self._mark_stack.append((self.stream_pos, self.bit_offset))

    def reset(self) -> None:
        """
        Pop the most recent mark and restore the position.

        Mirrors ``ImageInputStreamImpl.reset()``; if no mark was set the
        position is left unchanged (the JDK behaviour for an empty mark stack).
        """
        self._check_closed()
        if not self._mark_stack:
            return
        self.stream_pos, self.bit_offset = self._mark_stack.pop()

    def skip_bytes(self, n: int) -> int:
        """Advance up to ``n`` bytes; returns the count actually skipped."""
        self._check_closed()
        self.bit_offset = 0
        available = len(self._data) - self.stream_pos
        skipped = max(0, min(n, available))
        self.stream_pos += skipped
        return skipped

    def close(self) -> None:
        """Mark the stream closed; subsequent operations raise ``OSError``."""
        if self._closed:
            raise OSError("closed")
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    def _check_closed(self) -> None:
        if self._closed:
            raise OSError("closed")

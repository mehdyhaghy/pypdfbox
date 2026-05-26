from __future__ import annotations

from pypdfbox.jbig2.io.image_input_stream import EOF, ImageInputStream


class SubInputStream(ImageInputStream):
    """
    A wrapper for an :class:`ImageInputStream` providing a view of a specific
    part of the wrapped stream.

    Mirrors ``org.apache.pdfbox.jbig2.io.SubInputStream`` (which extends
    ``ImageInputStreamImpl``). It exposes the window ``[offset, offset+length)``
    of ``iis`` as a stream whose positions are *relative* to ``offset``. Only
    the byte-level reads (:meth:`read`, :meth:`read_full`), :meth:`length` and
    the extra :meth:`skip_bits` need overriding; the bit-level reads
    (:meth:`read_bit` / :meth:`read_bits`) are inherited and operate through
    :meth:`read`, exactly as in the JDK / upstream.

    Upstream synchronizes read accesses to the wrapped stream so callers need
    not coordinate against other users of the same wrapped instance. The Python
    port is single-threaded by contract (the decoder runs serially), so the
    explicit lock is omitted; the seek-before-read discipline that makes the
    sharing safe is preserved.
    """

    _BUFFER_SIZE = 4096

    def __init__(self, iis: ImageInputStream, offset: int, length: int) -> None:
        if iis is None:
            raise ValueError("Stream must not be null")
        if offset < 0:
            raise ValueError("Offset must be >= 0")
        if length < 0:
            raise ValueError("Length must be >= 0")

        # Do NOT chain to ImageInputStream.__init__ with byte data — this
        # subclass is backed by the wrapped stream, not its own buffer.
        self.wrapped_stream = iis
        self.offset = offset
        self._length = length

        self.stream_pos = 0
        self.bit_offset = 0
        self._closed = False
        self._mark_stack = []

        # A buffer used to improve read performance.
        self._buffer = bytearray(self._BUFFER_SIZE)
        # Location of the first byte in the buffer w.r.t. the start of the
        # (sub-)stream.
        self.buffer_base = 0
        # Location one past the last buffered byte w.r.t. the start of the
        # (sub-)stream.
        self.buffer_top = 0

    def read(self) -> int:
        self._check_closed()
        # ImageInputStreamImpl.read() always clears the pending bit offset.
        self.bit_offset = 0
        if self.stream_pos >= self._length:
            return EOF

        if (
            self.stream_pos >= self.buffer_top or self.stream_pos < self.buffer_base
        ) and not self._fill_buffer():
            return EOF

        read = 0xFF & self._buffer[self.stream_pos - self.buffer_base]
        self.stream_pos += 1
        return read

    def read_full(self, b: bytearray, off: int = 0, length: int | None = None) -> int:
        if b is None:
            raise ValueError("buffer must not be null")
        if length is None:
            length = len(b) - off
        if off < 0 or length < 0 or off + length > len(b):
            raise IndexError("offset/length out of bounds")

        self._check_closed()
        self.bit_offset = 0

        if self.stream_pos >= self._length:
            return EOF

        target_pos = self.stream_pos + self.offset
        if self.wrapped_stream.get_stream_position() != target_pos:
            self.wrapped_stream.seek(target_pos)

        to_read = min(length, self._length - self.stream_pos)
        read = self.wrapped_stream.read_full(b, off, to_read)
        # Only advance the stream position if we are not at EOF.
        if read > 0:
            self.stream_pos += read
        return read

    def _fill_buffer(self) -> bool:
        """
        Fill the buffer at the current stream position.

        Returns ``True`` on success, ``False`` at end of stream.
        """
        target_pos = self.stream_pos + self.offset
        if self.wrapped_stream.get_stream_position() != target_pos:
            self.wrapped_stream.seek(target_pos)

        self.buffer_base = self.stream_pos
        to_read = min(len(self._buffer), self._length - self.stream_pos)
        read = self.wrapped_stream.read_full(self._buffer, 0, to_read)
        if read > 0:
            self.buffer_top = self.buffer_base + read
        return read > 0

    def length(self) -> int:
        return self._length

    def skip_bytes(self, n: int) -> int:
        """Advance up to ``n`` bytes within the window; return the count skipped.

        Mirrors ``ImageInputStreamImpl.skipBytes(int)``: it clears any pending
        bit offset and advances the position, bounded by the window length. The
        base class implementation reads its own ``_data`` buffer, which this
        wrapped view does not own, so it is overridden here.
        """
        self._check_closed()
        self.bit_offset = 0
        available = self._length - self.stream_pos
        skipped = max(0, min(n, available))
        self.stream_pos += skipped
        return skipped

    def skip_bits(self) -> None:
        """
        Skip the remaining bits in the current byte.

        Mirrors upstream ``skipBits()``: if a partial byte is pending, drop the
        leftover bits and advance to the next byte (bounded by the window
        length).
        """
        if self.bit_offset != 0:
            self.bit_offset = 0
            if self.stream_pos < self._length:
                self.stream_pos += 1

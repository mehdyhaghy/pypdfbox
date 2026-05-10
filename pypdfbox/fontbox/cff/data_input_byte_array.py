from __future__ import annotations

import struct

from .data_input import DataInput


class DataInputByteArray(DataInput):
    """:class:`DataInput` implementation backed by an in-memory ``bytes`` buffer.

    Mirrors ``org.apache.fontbox.cff.DataInputByteArray``. The upstream
    Java class stores a ``byte[]`` plus an ``int bufferPosition``; we use
    a ``bytes`` buffer plus a Python int with the same semantics.

    Library-first: multi-byte reads delegate to :mod:`struct` for the
    big-endian decoding, but the public surface — including the
    error-raising semantics on EOF / out-of-range positions — matches
    upstream exactly.
    """

    def __init__(self, buffer: bytes | bytearray | memoryview) -> None:
        # Upstream stores the byte[] reference directly. We coerce to
        # immutable ``bytes`` so callers cannot mutate the parser's view
        # after construction.
        self._buffer: bytes = bytes(buffer)
        self._position: int = 0

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------
    def has_remaining(self) -> bool:
        return self._position < len(self._buffer)

    def get_position(self) -> int:
        return self._position

    def set_position(self, position: int) -> None:
        if position < 0:
            raise OSError("position is negative")
        if position >= len(self._buffer):
            # Upstream uses ``>=`` (strict) here — set_position(length) is
            # rejected even though it would just put the cursor at EOF.
            # Preserve that exactly so parser tests behave identically.
            raise OSError(
                f"New position is out of range {position} >= {len(self._buffer)}"
            )
        self._position = position

    def length(self) -> int:
        return len(self._buffer)

    # ------------------------------------------------------------------
    # Byte-level reads
    # ------------------------------------------------------------------
    def read_byte(self) -> int:
        if not self.has_remaining():
            raise OSError("End off buffer reached")
        # Mirror Java ``byte`` (signed, [-128, 127]).
        b = self._buffer[self._position]
        self._position += 1
        if b >= 0x80:
            b -= 0x100
        return b

    def read_unsigned_byte(self) -> int:
        if not self.has_remaining():
            raise OSError("End off buffer reached")
        b = self._buffer[self._position]
        self._position += 1
        return b

    def peek_unsigned_byte(self, offset: int) -> int:
        if offset < 0:
            raise OSError("offset is negative")
        target = self._position + offset
        if target >= len(self._buffer):
            raise OSError(
                f"Offset position is out of range {target} >= {len(self._buffer)}"
            )
        return self._buffer[target]

    def read_bytes(self, length: int) -> bytes:
        if length < 0:
            raise OSError("length is negative")
        if len(self._buffer) - self._position < length:
            raise OSError("Premature end of buffer reached")
        chunk = self._buffer[self._position : self._position + length]
        self._position += length
        return chunk

    # ------------------------------------------------------------------
    # struct-backed multi-byte fast paths (override the DataInput defaults
    # for in-memory speed; behaviour stays identical to the byte-by-byte
    # default implementations).
    # ------------------------------------------------------------------
    def read_unsigned_short(self) -> int:
        if len(self._buffer) - self._position < 2:
            # Trigger the same error message the byte-level path would,
            # so callers see one consistent EOF message.
            raise OSError("End off buffer reached")
        (value,) = struct.unpack_from(">H", self._buffer, self._position)
        self._position += 2
        return value

    def read_short(self) -> int:
        if len(self._buffer) - self._position < 2:
            raise OSError("End off buffer reached")
        (value,) = struct.unpack_from(">h", self._buffer, self._position)
        self._position += 2
        return value

    def read_int(self) -> int:
        if len(self._buffer) - self._position < 4:
            raise OSError("End off buffer reached")
        (value,) = struct.unpack_from(">i", self._buffer, self._position)
        self._position += 4
        return value

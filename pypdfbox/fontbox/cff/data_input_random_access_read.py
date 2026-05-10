from __future__ import annotations

from pypdfbox.io.random_access_read import RandomAccessRead

from .data_input import DataInput


class DataInputRandomAccessRead(DataInput):
    """:class:`DataInput` implementation backed by a :class:`RandomAccessRead`.

    Mirrors ``org.apache.fontbox.cff.DataInputRandomAccessRead``. Used by
    the parser when the CFF stream sits inside a larger random-access
    source (e.g. an OpenType ``CFF`` table inside a TrueType file).

    Note: things can get hairy when the underlying buffer is larger than
    ``Integer.MAX_VALUE``. Straight forward reading may work, but
    :meth:`get_position` and :meth:`set_position` may have problems —
    same caveat as upstream (Java ``int`` ceiling carried over).
    """

    def __init__(self, random_access_read: RandomAccessRead) -> None:
        self._random_access_read: RandomAccessRead = random_access_read

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------
    def has_remaining(self) -> bool:
        return self._random_access_read.available() > 0

    def get_position(self) -> int:
        return int(self._random_access_read.get_position())

    def set_position(self, position: int) -> None:
        if position < 0:
            raise OSError("position is negative")
        total = self._random_access_read.length()
        if position >= total:
            # Strict ``>=``, matching upstream — see DataInputByteArray.
            raise OSError(f"New position is out of range {position} >= {total}")
        self._random_access_read.seek(position)

    def length(self) -> int:
        return int(self._random_access_read.length())

    # ------------------------------------------------------------------
    # Byte-level reads
    # ------------------------------------------------------------------
    def read_byte(self) -> int:
        if not self.has_remaining():
            raise OSError("End of buffer reached!")
        b = self._random_access_read.read()
        # ``RandomAccessRead.read`` returns 0..255; convert to signed byte.
        if b >= 0x80:
            b -= 0x100
        return b

    def read_unsigned_byte(self) -> int:
        if not self.has_remaining():
            raise OSError("End of buffer reached!")
        return self._random_access_read.read()

    def peek_unsigned_byte(self, offset: int) -> int:
        if offset < 0:
            raise OSError("offset is negative")
        if offset == 0:
            # Fast path — peek() is O(1) and avoids the seek-restore dance.
            value = self._random_access_read.peek()
            if value == RandomAccessRead.EOF:
                # Match upstream: peek() at EOF surfaces as an out-of-range
                # error from peek_unsigned_byte.
                raise OSError(
                    "Offset position is out of range "
                    f"{self._random_access_read.get_position()} "
                    f">= {self._random_access_read.length()}"
                )
            return value
        current = self._random_access_read.get_position()
        total = self._random_access_read.length()
        if current + offset >= total:
            raise OSError(
                f"Offset position is out of range {current + offset} >= {total}"
            )
        self._random_access_read.seek(current + offset)
        peek_value = self._random_access_read.read()
        self._random_access_read.seek(current)
        return peek_value

    def read_bytes(self, length: int) -> bytes:
        if length < 0:
            raise OSError("length is negative")
        # Upstream tests assert that a failed ``read_bytes`` (overlong or
        # short) leaves the position unchanged — the next call still sees
        # the original cursor. ``RandomAccessRead.read_fully`` would
        # advance the cursor up to EOF before raising, so we range-check
        # ourselves first.
        if self._random_access_read.available() < length:
            raise OSError("Premature end of buffer reached")
        try:
            return self._random_access_read.read_fully(length)  # type: ignore[return-value]
        except EOFError as exc:
            # Defensive: should not be reachable given the available()
            # check above, but mirror upstream IOException semantics if it
            # ever does fire (e.g. concurrent truncation of the source).
            raise OSError("Premature end of buffer reached") from exc

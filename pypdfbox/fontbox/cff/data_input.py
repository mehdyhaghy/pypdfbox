from __future__ import annotations

from abc import ABC, abstractmethod


class DataInput(ABC):
    """Sequential big-endian reader used by the CFF parser.

    Mirrors the upstream interface ``org.apache.fontbox.cff.DataInput``.
    Java declares this as an interface with several ``default`` methods —
    in Python we model it as an ABC where the four "primitive" methods
    are abstract and the wider readers (``read_short`` /
    ``read_unsigned_short`` / ``read_int`` / ``read_offset``) are
    concrete and built on top of ``read_unsigned_byte``, exactly as
    upstream does.

    All multi-byte reads are big-endian, matching the CFF spec
    (Adobe Technical Note #5176 §5).
    """

    # ------------------------------------------------------------------
    # Abstract methods — implementations must provide these.
    # ------------------------------------------------------------------
    @abstractmethod
    def has_remaining(self) -> bool:
        """Return ``True`` if there are any bytes left to read."""

    @abstractmethod
    def get_position(self) -> int:
        """Return the current read offset."""

    @abstractmethod
    def set_position(self, position: int) -> None:
        """Set the current read offset.

        Raises ``OSError`` (Python equivalent of ``IOException``) if the
        new position is out of range.
        """

    @abstractmethod
    def read_byte(self) -> int:
        """Read one signed byte. Returned as a Python int in [-128, 127]."""

    @abstractmethod
    def read_unsigned_byte(self) -> int:
        """Read one unsigned byte. Returned as a Python int in [0, 255]."""

    @abstractmethod
    def peek_unsigned_byte(self, offset: int) -> int:
        """Peek the unsigned byte at ``current_position + offset``.

        Does not advance the position. ``offset`` must be ``>= 0``.
        """

    @abstractmethod
    def read_bytes(self, length: int) -> bytes:
        """Read exactly ``length`` bytes.

        Raises ``OSError`` if fewer than ``length`` bytes remain or if
        ``length`` is negative — upstream ``readBytes`` is all-or-nothing,
        never returning a short read.
        """

    @abstractmethod
    def length(self) -> int:
        """Total length of the underlying buffer in bytes."""

    # ------------------------------------------------------------------
    # Default implementations — match the Java ``default`` methods.
    # ------------------------------------------------------------------
    def read_short(self) -> int:
        """Read a signed 16-bit big-endian short. Returned in [-32768, 32767]."""
        value = self.read_unsigned_short()
        if value >= 0x8000:
            value -= 0x10000
        return value

    def read_unsigned_short(self) -> int:
        """Read an unsigned 16-bit big-endian short."""
        b1 = self.read_unsigned_byte()
        b2 = self.read_unsigned_byte()
        return (b1 << 8) | b2

    def read_int(self) -> int:
        """Read a signed 32-bit big-endian int (Java semantics)."""
        b1 = self.read_unsigned_byte()
        b2 = self.read_unsigned_byte()
        b3 = self.read_unsigned_byte()
        b4 = self.read_unsigned_byte()
        value = (b1 << 24) | (b2 << 16) | (b3 << 8) | b4
        # Java ``int`` is signed; mirror that so callers comparing against
        # negative literals (as the upstream tests do) get matching results.
        if value >= 0x8000_0000:
            value -= 0x1_0000_0000
        return value

    def read_offset(self, off_size: int) -> int:
        """Read a CFF ``Offset`` of ``off_size`` bytes (1..4), big-endian.

        Per CFF spec §5, ``OffSize`` is between 1 and 4 inclusive — this
        helper does not validate that range (the caller, ``CFFParser``,
        rejects out-of-band values), it simply assembles the bytes.
        """
        value = 0
        for _ in range(off_size):
            value = (value << 8) | self.read_unsigned_byte()
        return value

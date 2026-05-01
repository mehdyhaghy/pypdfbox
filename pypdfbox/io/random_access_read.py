from __future__ import annotations

from abc import ABC, abstractmethod


class RandomAccessRead(ABC):
    """
    Source of bytes that supports random-access reads (seek, peek, rewind).

    Mirrors org.apache.pdfbox.io.RandomAccessRead. Single-byte read() returns
    an int 0..255 or -1 at EOF, matching the Java API. Bulk reads use
    read_into() against a caller-provided bytearray.

    Subclasses must implement: read, read_into, get_position, seek, length,
    close, is_closed.
    """

    EOF: int = -1

    @abstractmethod
    def read(self) -> int:
        """Read a single byte. Returns 0..255, or -1 at EOF."""

    @abstractmethod
    def read_into(
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        """
        Read bytes into ``buf`` starting at ``offset``.

        ``length`` defaults to ``len(buf) - offset``. Returns the number of
        bytes actually read, or -1 if no bytes were read because EOF was
        already reached.
        """

    @abstractmethod
    def get_position(self) -> int:
        """Current read offset."""

    @abstractmethod
    def seek(self, position: int) -> None:
        """Set the read offset. ``position`` must be in [0, length()]."""

    @abstractmethod
    def length(self) -> int:
        """Total length in bytes."""

    @abstractmethod
    def close(self) -> None:
        """Release underlying resources. Idempotent."""

    @abstractmethod
    def is_closed(self) -> bool:
        ...

    def peek(self) -> int:
        """Read one byte without advancing position. Returns 0..255 or -1."""
        b = self.read()
        if b != self.EOF:
            self.rewind(1)
        return b

    def rewind(self, n: int) -> None:
        """Move position back by ``n`` bytes. ``n`` must be >= 0."""
        if n < 0:
            raise ValueError("rewind count must be non-negative")
        self.seek(self.get_position() - n)

    def is_eof(self) -> bool:
        return self.get_position() >= self.length()

    def read_fully(
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> None:
        """
        Read exactly ``length`` bytes into ``buf`` starting at ``offset``.
        Raises ``EOFError`` if EOF is reached before ``length`` bytes are read.
        Mirrors ``DataInput.readFully`` / PDFBox's ``RandomAccessRead.readFully``.
        """
        if length is None:
            length = len(buf) - offset
        if length < 0:
            raise ValueError("length must be non-negative")
        if offset < 0 or offset + length > len(buf):
            raise ValueError("offset/length out of range for buf")
        total = 0
        while total < length:
            n = self.read_into(buf, offset + total, length - total)
            if n <= 0:
                raise EOFError("EOF reached before reading requested length")
            total += n

    def skip(self, n: int) -> None:
        """Advance position by ``n`` bytes (clipped to length)."""
        if n < 0:
            raise ValueError("skip count must be non-negative")
        target = min(self.get_position() + n, self.length())
        self.seek(target)

    def available(self) -> int:
        return self.length() - self.get_position()

    def unread(self, b: int | bytes | bytearray | memoryview) -> None:
        """
        Push bytes back into the stream. In PDFBox semantics this simply
        rewinds the position; the caller-supplied bytes are not actually
        re-stored — they are assumed to match what was previously read.
        """
        if isinstance(b, int):
            self.rewind(1)
        else:
            self.rewind(len(b))

    def create_view(self, start_position: int, length: int) -> RandomAccessRead:
        """
        Return a read-only slice view onto this stream covering bytes
        ``[start_position, start_position + length)``.

        The view shares this stream's underlying storage; callers must not
        interleave reads on the parent and the view in performance-sensitive
        code (each view operation seeks the parent to its own logical
        position).
        """
        # Deferred import to avoid cycle: View depends on this ABC.
        from .random_access_read_view import RandomAccessReadView

        return RandomAccessReadView(self, start_position, length)

    def __enter__(self) -> RandomAccessRead:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Upstream Java aliases (camelCase mirrors of the snake_case API).
    # Provided so PDFBox developers can call the names they know; semantics
    # are unchanged. Not enumerated in __all__; they are method aliases only.
    # ------------------------------------------------------------------

    def getPosition(self) -> int:  # noqa: N802 — upstream Java alias
        return self.get_position()

    def isClosed(self) -> bool:  # noqa: N802 — upstream Java alias
        return self.is_closed()

    def isEOF(self) -> bool:  # noqa: N802 — upstream Java alias
        return self.is_eof()

    def readFully(  # noqa: N802 — upstream Java alias
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> None:
        self.read_fully(buf, offset, length)

    def createView(  # noqa: N802 — upstream Java alias
        self, start_position: int, length: int
    ) -> RandomAccessRead:
        return self.create_view(start_position, length)

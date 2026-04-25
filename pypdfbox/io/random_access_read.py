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

    def __enter__(self) -> RandomAccessRead:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

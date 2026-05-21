from __future__ import annotations

from abc import ABC, abstractmethod


class RandomAccessWrite(ABC):
    """
    Sink of bytes that supports the PDFBox random-access write contract.

    Mirrors org.apache.pdfbox.io.RandomAccessWrite. Subclasses must
    implement: write, write_bytes, clear, close, is_closed.
    """

    @abstractmethod
    def write(self, b: int) -> None:
        """Write a single byte. ``b`` must be in 0..255."""

    @abstractmethod
    def write_bytes(
        self, data: bytes | bytearray | memoryview, offset: int = 0, length: int | None = None
    ) -> None:
        """
        Write ``length`` bytes from ``data`` starting at ``offset``.
        ``length`` defaults to ``len(data) - offset``.
        """

    @abstractmethod
    def clear(self) -> None:
        """Discard any buffered output and reset position to zero."""

    @abstractmethod
    def close(self) -> None:
        """Release underlying resources. Idempotent."""

    @abstractmethod
    def is_closed(self) -> bool:
        ...

    def __enter__(self) -> RandomAccessWrite:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

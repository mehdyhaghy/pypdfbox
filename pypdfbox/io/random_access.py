from __future__ import annotations

from abc import abstractmethod

from .random_access_read import RandomAccessRead
from .random_access_write import RandomAccessWrite


class RandomAccess(RandomAccessRead, RandomAccessWrite):
    """Combined random-access reader/writer interface.

    Mirrors upstream ``org.apache.pdfbox.io.RandomAccess`` which extends
    both ``RandomAccessRead`` and ``RandomAccessWrite``. Concrete
    in-memory implementations (e.g. ``RandomAccessReadWriteBuffer``)
    subclass this so callers can both seek-and-read and seek-and-write
    against the same buffer.
    """

    @abstractmethod
    def clear(self) -> None:
        """Reset position to zero and discard all stored bytes.

        Mirrors upstream ``RandomAccessWrite.clear`` (also re-declared
        on ``RandomAccess`` for convenience).
        """

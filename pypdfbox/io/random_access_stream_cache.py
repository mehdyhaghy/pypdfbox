from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .random_access import RandomAccess


class RandomAccessStreamCache(ABC):
    """Pluggable cache that hands out scratch ``RandomAccess`` buffers.

    Mirrors upstream
    ``org.apache.pdfbox.io.RandomAccessStreamCache`` (an interface).
    Implementations decide where the buffer lives (memory, scratch file,
    hybrid) — the writer doesn't care.
    """

    @abstractmethod
    def create_buffer(self) -> RandomAccess:
        """Allocate a new ``RandomAccess`` buffer.

        Mirrors upstream ``createBuffer`` (Java line 48). The caller is
        responsible for closing the buffer; if it doesn't, the buffer
        will be closed when this cache itself is closed.
        """

    def close(self) -> None:  # noqa: B027 — explicit no-op default matches upstream
        """Release any resources held by the cache.

        Mirrors upstream ``Closeable.close``. Default is a no-op so
        purely in-memory caches don't need to override.
        """

    def __enter__(self) -> RandomAccessStreamCache:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

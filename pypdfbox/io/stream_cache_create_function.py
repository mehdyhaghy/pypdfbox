from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .random_access_stream_cache import RandomAccessStreamCache


@runtime_checkable
class StreamCacheCreateFunction(Protocol):
    """Callable factory that creates a fresh ``RandomAccessStreamCache``.

    Mirrors upstream
    ``org.apache.pdfbox.io.RandomAccessStreamCache.StreamCacheCreateFunction``
    (a nested ``@FunctionalInterface`` on the cache interface). Python
    callers can pass any zero-argument callable returning a stream cache;
    a ``Protocol`` is used so duck-typing-style callbacks satisfy the type.
    """

    def create(self) -> RandomAccessStreamCache:
        """Mirrors upstream ``StreamCacheCreateFunction.create``."""
        ...

    def __call__(self) -> RandomAccessStreamCache: ...


# Convenience alias for callers that prefer the structural type.
StreamCacheCreateCallable = Callable[[], "RandomAccessStreamCache"]

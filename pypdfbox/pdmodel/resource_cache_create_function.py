from __future__ import annotations

from typing import Protocol, runtime_checkable

from .resource_cache import ResourceCache


@runtime_checkable
class ResourceCacheCreateFunction(Protocol):
    """Functional interface for creating :class:`ResourceCache` instances.

    Mirrors ``org.apache.pdfbox.pdmodel.ResourceCacheCreateFunction``
    (Java lines 24-32). Implementations supply a no-argument ``create``
    factory used by :class:`ResourceCacheFactory` to spin up a new cache
    per document.
    """

    def create(self) -> ResourceCache:
        """Return a fresh :class:`ResourceCache` instance."""
        ...


__all__ = ["ResourceCacheCreateFunction"]

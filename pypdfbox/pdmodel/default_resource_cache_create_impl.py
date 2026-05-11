from __future__ import annotations

from .pd_resource_cache import DefaultResourceCache
from .resource_cache import ResourceCache


class DefaultResourceCacheCreateImpl:
    """Default :class:`ResourceCacheCreateFunction` — produces
    :class:`DefaultResourceCache` instances.

    Mirrors ``org.apache.pdfbox.pdmodel.DefaultResourceCacheCreateImpl``
    (Java lines 24-51).
    """

    def __init__(self, enable_stable_cache: bool = True) -> None:
        """Mirrors upstream's two constructors (Java lines 31 and 42).

        Pass ``enable_stable_cache=False`` to disable the stable object
        cache (font/colour-space pinning across removals)."""
        self._stable_cache_enabled: bool = enable_stable_cache

    def create(self) -> ResourceCache:
        """Create a fresh :class:`DefaultResourceCache`. Mirrors upstream
        ``create()`` (Java line 48)."""
        return DefaultResourceCache(self._stable_cache_enabled)


__all__ = ["DefaultResourceCacheCreateImpl"]

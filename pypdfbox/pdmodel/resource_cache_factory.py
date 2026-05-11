from __future__ import annotations

from .default_resource_cache_create_impl import DefaultResourceCacheCreateImpl
from .resource_cache import ResourceCache
from .resource_cache_create_function import ResourceCacheCreateFunction


class ResourceCacheFactory:
    """Process-wide factory for :class:`ResourceCache` instances.

    Mirrors ``org.apache.pdfbox.pdmodel.ResourceCacheFactory`` (Java
    lines 28-66). Holds a single :class:`ResourceCacheCreateFunction` —
    set this to ``None`` to disable resource caching globally.

    Java uses static state; Python mirrors that as class attributes so the
    upstream API (``ResourceCacheFactory.set_resource_cache_create_function``)
    works without instantiating the factory.
    """

    _resource_cache_create_function: ResourceCacheCreateFunction | None = (
        DefaultResourceCacheCreateImpl()
    )

    @classmethod
    def set_resource_cache_create_function(
        cls, function: ResourceCacheCreateFunction | None
    ) -> None:
        """Replace the active factory function. Mirrors upstream
        ``setResourceCacheCreateFunction`` (Java line 41)."""
        cls._resource_cache_create_function = function

    @classmethod
    def get_resource_cache_create_function(
        cls,
    ) -> ResourceCacheCreateFunction | None:
        """Return the active factory function (or ``None`` when caching
        is disabled). Mirrors upstream ``getResourceCacheCreateFunction``
        (Java line 51)."""
        return cls._resource_cache_create_function

    @classmethod
    def create_resource_cache(cls) -> ResourceCache | None:
        """Build a new :class:`ResourceCache` via the active factory
        function, or return ``None`` when caching is disabled.

        Mirrors upstream ``createResourceCache`` (Java line 61).
        """
        function = cls._resource_cache_create_function
        if function is None:
            return None
        return function.create()


__all__ = ["ResourceCacheFactory"]

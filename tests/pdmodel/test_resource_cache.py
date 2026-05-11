from __future__ import annotations

from pypdfbox.pdmodel import ResourceCache
from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache


def test_resource_cache_subclasses_pd_resource_cache() -> None:
    assert issubclass(ResourceCache, PDResourceCache)


def test_resource_cache_is_abstract() -> None:
    import inspect

    assert inspect.isabstract(ResourceCache)

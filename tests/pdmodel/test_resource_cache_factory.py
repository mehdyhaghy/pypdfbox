from __future__ import annotations

import pytest

from pypdfbox.pdmodel import (
    DefaultResourceCacheCreateImpl,
    ResourceCacheFactory,
)
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


@pytest.fixture(autouse=True)
def _restore_factory():
    saved = ResourceCacheFactory.get_resource_cache_create_function()
    yield
    ResourceCacheFactory.set_resource_cache_create_function(saved)


def test_default_factory_is_default_impl() -> None:
    fn = ResourceCacheFactory.get_resource_cache_create_function()
    assert isinstance(fn, DefaultResourceCacheCreateImpl)


def test_create_resource_cache_returns_default() -> None:
    cache = ResourceCacheFactory.create_resource_cache()
    assert isinstance(cache, DefaultResourceCache)


def test_set_to_none_disables_creation() -> None:
    ResourceCacheFactory.set_resource_cache_create_function(None)
    assert ResourceCacheFactory.create_resource_cache() is None


def test_replace_with_custom_function() -> None:
    class _Custom:
        def create(self) -> DefaultResourceCache:
            return DefaultResourceCache(False)

    ResourceCacheFactory.set_resource_cache_create_function(_Custom())
    cache = ResourceCacheFactory.create_resource_cache()
    assert isinstance(cache, DefaultResourceCache)
    assert cache._stable_cache_enabled is False

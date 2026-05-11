from __future__ import annotations

from pypdfbox.pdmodel import DefaultResourceCacheCreateImpl
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


def test_default_constructor_enables_stable_cache() -> None:
    impl = DefaultResourceCacheCreateImpl()
    cache = impl.create()
    assert isinstance(cache, DefaultResourceCache)


def test_disable_stable_cache_propagates() -> None:
    impl = DefaultResourceCacheCreateImpl(enable_stable_cache=False)
    cache = impl.create()
    # _stable_cache_enabled is private but accessible for testing.
    assert cache._stable_cache_enabled is False


def test_each_create_returns_fresh_instance() -> None:
    impl = DefaultResourceCacheCreateImpl()
    assert impl.create() is not impl.create()

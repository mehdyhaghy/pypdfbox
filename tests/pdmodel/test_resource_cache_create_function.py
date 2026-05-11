from __future__ import annotations

from pypdfbox.pdmodel import ResourceCacheCreateFunction
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


class _Impl:
    def create(self) -> DefaultResourceCache:
        return DefaultResourceCache()


def test_protocol_matches_implementation() -> None:
    impl = _Impl()
    assert isinstance(impl, ResourceCacheCreateFunction)
    cache = impl.create()
    assert isinstance(cache, DefaultResourceCache)


def test_protocol_rejects_unrelated() -> None:
    class _NoMethod:
        pass

    assert not isinstance(_NoMethod(), ResourceCacheCreateFunction)

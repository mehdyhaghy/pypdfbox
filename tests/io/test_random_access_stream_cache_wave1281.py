"""Wave 1281: RandomAccessStreamCache + Impl port."""

from __future__ import annotations

import pytest

from pypdfbox.io import (
    RandomAccess,
    RandomAccessStreamCache,
    RandomAccessStreamCacheImpl,
    StreamCacheCreateFunction,
)


def test_cache_impl_creates_random_access_buffer() -> None:
    cache = RandomAccessStreamCacheImpl()
    buf = cache.create_buffer()
    assert isinstance(buf, RandomAccess)
    buf.close()
    cache.close()


def test_cache_impl_is_stream_cache() -> None:
    assert isinstance(RandomAccessStreamCacheImpl(), RandomAccessStreamCache)


def test_abstract_class_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        RandomAccessStreamCache()  # type: ignore[abstract]


def test_stream_cache_create_function_protocol() -> None:
    # Mirrors the upstream functional-interface shape: a class exposing
    # both ``__call__`` and ``create`` satisfies the Protocol.
    class _Factory:
        def __call__(self) -> RandomAccessStreamCache:
            return RandomAccessStreamCacheImpl()

        def create(self) -> RandomAccessStreamCache:
            return self()

    factory = _Factory()
    assert isinstance(factory, StreamCacheCreateFunction)
    cache = factory()
    cache.close()

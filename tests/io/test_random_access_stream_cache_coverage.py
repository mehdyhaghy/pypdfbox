"""Coverage-boost tests for ``RandomAccessStreamCache``.

Specifically targets the context-manager methods (``__enter__`` /
``__exit__``) which the primary test file doesn't exercise.
"""
from __future__ import annotations

from pypdfbox.io import RandomAccessStreamCache, RandomAccessStreamCacheImpl


def test_context_manager_returns_self() -> None:
    cache = RandomAccessStreamCacheImpl()
    with cache as cm:
        assert cm is cache


def test_context_manager_calls_close_on_exit() -> None:
    closed: list[bool] = []

    class _RecordingCache(RandomAccessStreamCacheImpl):
        def close(self) -> None:  # type: ignore[override]
            closed.append(True)
            super().close()

    with _RecordingCache():
        pass

    assert closed == [True]


def test_context_manager_propagates_exception() -> None:
    closed: list[bool] = []

    class _RecordingCache(RandomAccessStreamCacheImpl):
        def close(self) -> None:  # type: ignore[override]
            closed.append(True)
            super().close()

    try:
        with _RecordingCache():
            raise ValueError("boom")
    except ValueError:
        pass

    assert closed == [True]


def test_default_close_is_noop_subclass() -> None:
    """A subclass that doesn't override ``close`` inherits the no-op."""

    class _MinimalCache(RandomAccessStreamCache):
        def create_buffer(self):  # type: ignore[override]
            return None

    cache = _MinimalCache()
    # Default close is a no-op — should not raise.
    cache.close()
    # And reusing the cache after ``close`` still works.
    cache.close()
    cache.close()


def test_context_manager_with_default_close() -> None:
    class _MinimalCache(RandomAccessStreamCache):
        def create_buffer(self):  # type: ignore[override]
            return None

    with _MinimalCache() as cm:
        assert isinstance(cm, RandomAccessStreamCache)

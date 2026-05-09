from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pypdfbox.multipdf import Splitter
from tests.multipdf import test_splitter_accessors as accessors


def test_existing_stream_cache_factory_body_is_executed(monkeypatch) -> None:
    original = Splitter.set_stream_cache_create_function
    calls = 0

    def set_and_probe_factory(
        self: Splitter,
        fn: Callable[[], Any] | None,
    ) -> Splitter:
        nonlocal calls
        if fn is not None:
            calls += 1
            assert fn() is None
        return original(self, fn)

    monkeypatch.setattr(
        Splitter,
        "set_stream_cache_create_function",
        set_and_probe_factory,
    )

    accessors.test_has_stream_cache_create_function_round_trip()
    assert calls == 1

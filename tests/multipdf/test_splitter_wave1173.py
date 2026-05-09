from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pypdfbox.multipdf import Splitter
from tests.multipdf import test_splitter


def test_wave1173_stream_cache_factory_return_branch(monkeypatch: Any) -> None:
    original_setter = Splitter.set_stream_cache_create_function

    def set_and_probe_cache_factory(
        self: Splitter,
        stream_cache_create_function: Callable[[], object | None],
    ) -> None:
        assert stream_cache_create_function() is None
        original_setter(self, stream_cache_create_function)

    monkeypatch.setattr(
        Splitter,
        "set_stream_cache_create_function",
        set_and_probe_cache_factory,
    )

    test_splitter.test_stream_cache_create_function_round_trips()

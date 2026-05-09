from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1101 as wave1101
from tests.rendering import test_pdf_renderer_wave1111 as wave1111


def test_wave1121_wave1111_restores_original_dispatch_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = wave1101._dispatch()
    previous = dispatch.get("W531")
    calls: list[str] = []

    def original_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        calls.append("original")

    dispatch["W531"] = original_handler
    try:
        wave1111.test_wave1111_wave1101_invokes_existing_handler_and_restores_seeded_prior(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is original_handler
        dispatch["W531"](None, object(), [])
        assert calls == ["original"]
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

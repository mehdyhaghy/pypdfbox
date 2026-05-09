from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1101 as wave1101


def test_wave1111_wave1101_invokes_existing_handler_and_restores_seeded_prior(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = wave1101._dispatch()
    original = dispatch.get("W531")
    calls: list[str] = []

    def seeded_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        calls.append("seeded")

    def invoke_wave1101_existing_handler(
        _caplog: Any,
        _monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        dispatch["W531"](None, object(), [])

    dispatch["W531"] = seeded_handler
    monkeypatch.setattr(
        wave1101.wave1091,
        "test_wave1081_invokes_local_handler_and_restores_prior",
        invoke_wave1101_existing_handler,
    )

    try:
        wave1101.test_wave1101_wave1091_restores_existing_dispatch_handler(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is seeded_handler
        dispatch["W531"](None, object(), [])
        assert calls == ["seeded"]
    finally:
        if original is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = original

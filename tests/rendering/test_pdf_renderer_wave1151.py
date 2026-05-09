from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1101 as wave1101
from tests.rendering import test_pdf_renderer_wave1141 as wave1141


def test_wave1151_wave1141_restores_outer_dispatch_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = wave1101._dispatch()
    previous = dispatch.get("W531")
    calls: list[str] = []

    def outer_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        calls.append("outer")

    dispatch["W531"] = outer_handler
    try:
        wave1141.test_wave1141_wave1131_restores_preexisting_dispatch_handler(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is outer_handler
        dispatch["W531"](None, object(), [])
        assert calls == ["outer"]
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

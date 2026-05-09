from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1101 as wave1101
from tests.rendering import test_pdf_renderer_wave1131 as wave1131


def test_wave1141_wave1131_restores_preexisting_dispatch_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = wave1101._dispatch()
    previous = dispatch.get("W531")
    calls: list[str] = []

    def preexisting_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        calls.append("preexisting")

    dispatch["W531"] = preexisting_handler
    try:
        wave1131.test_wave1131_wave1121_restores_seeded_dispatch_handler(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is preexisting_handler
        dispatch["W531"](None, object(), [])
        assert calls == ["preexisting"]
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

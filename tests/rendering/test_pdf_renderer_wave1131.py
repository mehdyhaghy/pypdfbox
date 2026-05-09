from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1101 as wave1101
from tests.rendering import test_pdf_renderer_wave1121 as wave1121


def test_wave1131_wave1121_restores_seeded_dispatch_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = wave1101._dispatch()
    previous = dispatch.get("W531")
    calls: list[str] = []

    def seeded_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        calls.append("seeded")

    dispatch["W531"] = seeded_handler
    try:
        wave1121.test_wave1121_wave1111_restores_original_dispatch_handler(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is seeded_handler
        dispatch["W531"](None, object(), [])
        assert calls == ["seeded"]
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

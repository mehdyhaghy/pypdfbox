from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1101 as wave1101
from tests.rendering import test_pdf_renderer_wave1151 as wave1151


def test_wave1161_wave1151_restores_seeded_dispatch_handler(
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
        wave1151.test_wave1151_wave1141_restores_outer_dispatch_handler(
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

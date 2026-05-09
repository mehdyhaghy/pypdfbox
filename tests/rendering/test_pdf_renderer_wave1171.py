from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1101 as wave1101
from tests.rendering import test_pdf_renderer_wave1161 as wave1161


def test_wave1171_wave1161_restores_handler_present_at_entry(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = wave1101._dispatch()
    previous = dispatch.get("W531")
    calls: list[str] = []

    def entry_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        calls.append("entry")

    dispatch["W531"] = entry_handler
    try:
        wave1161.test_wave1161_wave1151_restores_seeded_dispatch_handler(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is entry_handler
        dispatch["W531"](None, object(), [])
        assert calls == ["entry"]
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

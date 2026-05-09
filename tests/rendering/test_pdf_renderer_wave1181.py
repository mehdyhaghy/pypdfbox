from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1101 as wave1101
from tests.rendering import test_pdf_renderer_wave1171 as wave1171


def test_wave1181_wave1171_restores_handler_present_at_entry(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = wave1101._dispatch()
    calls: list[str] = []

    def outer_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        calls.append("outer")

    monkeypatch.setitem(dispatch, "W531", outer_handler)

    wave1171.test_wave1171_wave1161_restores_handler_present_at_entry(
        caplog,
        monkeypatch,
    )

    assert dispatch["W531"] is outer_handler
    dispatch["W531"](None, object(), [])
    assert calls == ["outer"]

from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1081 as wave1081


def test_wave1081_invokes_local_handler_and_restores_prior(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = (
        wave1081.wave1071.wave1061.wave1051.wave1041.wave1031.wave1021.wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )

    def previous_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise AssertionError("previous handler should only be restored")

    def call_current_handler(_caplog: Any, _monkeypatch: pytest.MonkeyPatch) -> None:
        dispatch["W531"](None, object(), [])

    original = dispatch.get("W531")
    dispatch["W531"] = previous_handler
    monkeypatch.setattr(
        wave1081.wave1071,
        "test_wave1061_restores_non_empty_previous_handler",
        call_current_handler,
    )
    try:
        wave1081.test_wave1071_restores_existing_original_handler(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is previous_handler
    finally:
        if original is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = original

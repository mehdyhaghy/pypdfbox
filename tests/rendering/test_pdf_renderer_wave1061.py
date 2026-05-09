from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1051 as wave1051


def _sentinel_handler(_renderer: Any, _op: object, _operands: list[object]) -> None:
    raise AssertionError("sentinel handler should be restored")


def test_wave1051_exercises_local_original_handler_and_restores_previous(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = (
        wave1051.wave1041.wave1031.wave1021.wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )

    def call_current_handler(_caplog: Any, _monkeypatch: pytest.MonkeyPatch) -> None:
        dispatch["W531"](None, object(), [])

    previous = dispatch.get("W531")
    dispatch["W531"] = _sentinel_handler
    monkeypatch.setattr(
        wave1051.wave1041,
        "test_wave1031_restores_existing_dispatch_handler",
        call_current_handler,
    )
    try:
        with pytest.raises(AssertionError, match="original handler"):
            wave1051.test_wave1041_restores_non_empty_original_handler(
                caplog,
                monkeypatch,
            )

        assert dispatch["W531"] is _sentinel_handler
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

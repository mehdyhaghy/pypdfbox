from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1091 as wave1091


def _dispatch() -> dict[str, Any]:
    return (
        wave1091.wave1081.wave1071.wave1061.wave1051.wave1041.wave1031.wave1021.wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )


def test_wave1101_wave1091_previous_handler_assertion_path(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = _dispatch()

    def invoke_wave1091_previous_handler(
        _caplog: Any,
        _monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        dispatch["W531"](None, object(), [])

    monkeypatch.setattr(
        wave1091.wave1081,
        "test_wave1071_restores_existing_original_handler",
        invoke_wave1091_previous_handler,
    )

    with pytest.raises(
        AssertionError,
        match="previous handler should only be restored",
    ):
        wave1091.test_wave1081_invokes_local_handler_and_restores_prior(
            caplog,
            monkeypatch,
        )


def test_wave1101_wave1091_restores_existing_dispatch_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = _dispatch()

    def existing_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        return None

    previous = dispatch.get("W531")
    dispatch["W531"] = existing_handler
    try:
        wave1091.test_wave1081_invokes_local_handler_and_restores_prior(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is existing_handler
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1021 as wave1021


def _raise_prior_handler_restored(
    _renderer: Any,
    _op: object,
    _operands: list[object],
) -> None:
    raise AssertionError("prior handler should be restored")


def test_wave1021_local_handler_raises_and_restores_prior_entry(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = (
        wave1021.wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )

    def call_wave1021_handler(_monkeypatch: pytest.MonkeyPatch, _caplog: Any) -> None:
        dispatch["W531"](None, object(), [])

    previous = dispatch.get("W531")
    dispatch["W531"] = _raise_prior_handler_restored
    monkeypatch.setattr(
        wave1021.wave1011,
        "test_wave1001_original_handler_raises_and_restores_previous",
        call_wave1021_handler,
    )
    try:
        with pytest.raises(
            AssertionError,
            match="outer original handler should be restored",
        ):
            wave1021.test_wave1011_previous_handler_is_exercised_before_restoring_original(
                monkeypatch,
                caplog,
            )

        assert dispatch["W531"] is _raise_prior_handler_restored
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

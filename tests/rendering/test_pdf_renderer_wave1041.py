from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1031 as wave1031


def _raise_existing_handler(
    _renderer: Any,
    _op: object,
    _operands: list[object],
) -> None:
    raise AssertionError("existing handler")


def test_wave1031_exposed_prior_handler_raises() -> None:
    with pytest.raises(AssertionError, match="prior handler should be restored"):
        wave1031._raise_prior_handler_restored(None, object(), [])  # noqa: SLF001


def test_wave1031_restores_existing_dispatch_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = (
        wave1031.wave1021.wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )

    old_handler = dispatch.get("W531")
    dispatch["W531"] = _raise_existing_handler
    try:
        wave1031.test_wave1021_local_handler_raises_and_restores_prior_entry(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is _raise_existing_handler
    finally:
        if old_handler is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = old_handler

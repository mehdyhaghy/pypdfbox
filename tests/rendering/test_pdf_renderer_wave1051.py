from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1041 as wave1041


def test_wave1041_exposed_existing_handler_raises() -> None:
    with pytest.raises(AssertionError, match="existing handler"):
        wave1041._raise_existing_handler(None, object(), [])  # noqa: SLF001


def test_wave1041_restores_non_empty_original_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = (
        wave1041.wave1031.wave1021.wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )

    def original_handler(_renderer: Any, _op: object, _operands: list[object]) -> None:
        raise AssertionError("original handler")

    previous = dispatch.get("W531")
    dispatch["W531"] = original_handler
    try:
        wave1041.test_wave1031_restores_existing_dispatch_handler(caplog, monkeypatch)

        assert dispatch["W531"] is original_handler
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

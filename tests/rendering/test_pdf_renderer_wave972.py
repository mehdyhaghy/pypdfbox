from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave966 as wave966


def _raise_restored_sentinel(
    _renderer: wave966.wave531.PDFRenderer,
    _op: object,
    _operands: list[object],
) -> None:
    raise AssertionError("sentinel should be restored only")


def test_wave966_restores_previous_handler_after_calling_local_handler(
    monkeypatch: Any,
    caplog: Any,
) -> None:
    def call_current_handler(_caplog: Any) -> None:
        handler = wave966.wave531.renderer_mod._DISPATCH["W531"]
        handler(None, object(), [])

    original = wave966.wave531.renderer_mod._DISPATCH.get("W531")
    wave966.wave531.renderer_mod._DISPATCH["W531"] = _raise_restored_sentinel
    monkeypatch.setattr(
        wave966.wave531,
        "test_process_operator_logs_and_swallows_handler_value_error",
        call_current_handler,
    )
    try:
        with pytest.raises(AssertionError, match="should be restored"):
            wave966.test_wave531_dispatch_test_restores_existing_handler(caplog)

        assert wave966.wave531.renderer_mod._DISPATCH["W531"] is _raise_restored_sentinel
    finally:
        if original is None:
            wave966.wave531.renderer_mod._DISPATCH.pop("W531", None)
        else:
            wave966.wave531.renderer_mod._DISPATCH["W531"] = original

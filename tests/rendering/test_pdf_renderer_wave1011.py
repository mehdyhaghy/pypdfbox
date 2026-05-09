from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1001 as wave1001


def test_wave1001_original_handler_raises_and_restores_previous(
    monkeypatch: pytest.MonkeyPatch,
    caplog: Any,
) -> None:
    def previous_handler(
        _renderer: wave1001.wave991.wave981.wave972.wave966.wave531.PDFRenderer,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise AssertionError("previous handler should be restored after failure")

    def call_current_handler(_monkeypatch: Any, _caplog: Any) -> None:
        handler = wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH[
            "W531"
        ]
        handler(None, object(), [])

    dispatch = wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    original = dispatch.get("W531")
    dispatch["W531"] = previous_handler
    monkeypatch.setattr(
        wave1001.wave991,
        "test_wave981_original_handler_raise_restores_existing_previous",
        call_current_handler,
    )
    try:
        with pytest.raises(
            AssertionError,
            match="original handler should only be restored",
        ):
            wave1001.test_wave991_restores_non_empty_original_handler(
                monkeypatch,
                caplog,
            )

        assert dispatch["W531"] is previous_handler
    finally:
        if original is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = original

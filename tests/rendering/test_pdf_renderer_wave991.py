from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave981 as wave981


def _raise_previous_handler(
    _renderer: wave981.wave972.wave966.wave531.PDFRenderer,
    _op: object,
    _operands: list[object],
) -> None:
    raise AssertionError("previous handler should only be restored")


def test_wave981_original_handler_raise_restores_existing_previous(
    monkeypatch: pytest.MonkeyPatch,
    caplog: Any,
) -> None:
    def call_current_handler(_monkeypatch: Any, _caplog: Any) -> None:
        handler = wave981.wave972.wave966.wave531.renderer_mod._DISPATCH["W531"]  # noqa: SLF001
        handler(None, object(), [])

    dispatch = wave981.wave972.wave966.wave531.renderer_mod._DISPATCH  # noqa: SLF001
    original = dispatch.get("W531")
    dispatch["W531"] = _raise_previous_handler
    monkeypatch.setattr(
        wave981.wave972,
        "test_wave966_restores_previous_handler_after_calling_local_handler",
        call_current_handler,
    )
    try:
        with pytest.raises(AssertionError, match="original should only be restored"):
            wave981.test_wave972_restores_non_empty_original_handler(
                monkeypatch,
                caplog,
            )

        assert dispatch["W531"] is _raise_previous_handler
    finally:
        if original is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = original

from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave972 as wave972


def test_wave972_exposed_sentinel_raises() -> None:
    with pytest.raises(AssertionError, match="sentinel should be restored"):
        wave972._raise_restored_sentinel(None, object(), [])


def test_wave972_restores_non_empty_original_handler(
    monkeypatch: Any,
    caplog: Any,
) -> None:
    def original_handler(
        _renderer: wave972.wave966.wave531.PDFRenderer,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise AssertionError("original should only be restored")

    previous = wave972.wave966.wave531.renderer_mod._DISPATCH.get("W531")
    wave972.wave966.wave531.renderer_mod._DISPATCH["W531"] = original_handler
    try:
        wave972.test_wave966_restores_previous_handler_after_calling_local_handler(
            monkeypatch,
            caplog,
        )

        assert wave972.wave966.wave531.renderer_mod._DISPATCH["W531"] is original_handler
    finally:
        if previous is None:
            wave972.wave966.wave531.renderer_mod._DISPATCH.pop("W531", None)
        else:
            wave972.wave966.wave531.renderer_mod._DISPATCH["W531"] = previous

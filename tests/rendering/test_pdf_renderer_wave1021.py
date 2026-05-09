from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1011 as wave1011


def test_wave1011_previous_handler_is_exercised_before_restoring_original(
    monkeypatch: pytest.MonkeyPatch,
    caplog: Any,
) -> None:
    def original_handler(
        _renderer: wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.PDFRenderer,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise AssertionError("outer original handler should be restored")

    def raise_expected_after_calling_previous(
        _monkeypatch: pytest.MonkeyPatch,
        _caplog: Any,
    ) -> None:
        handler = dispatch["W531"]
        with pytest.raises(
            AssertionError,
            match="previous handler should be restored after failure",
        ):
            handler(None, object(), [])
        raise AssertionError("original handler should only be restored")

    dispatch = (
        wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )
    previous = dispatch.get("W531")
    dispatch["W531"] = original_handler
    monkeypatch.setattr(
        wave1011.wave1001,
        "test_wave991_restores_non_empty_original_handler",
        raise_expected_after_calling_previous,
    )
    try:
        wave1011.test_wave1001_original_handler_raises_and_restores_previous(
            monkeypatch,
            caplog,
        )

        assert dispatch["W531"] is original_handler
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

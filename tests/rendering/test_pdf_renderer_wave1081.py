from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1071 as wave1071


def test_wave1071_prior_handler_raises_expected_assertion() -> None:
    with pytest.raises(AssertionError, match="prior handler should be restored"):
        wave1071._prior_handler(None, object(), [])  # noqa: SLF001


def test_wave1071_restores_existing_original_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = (
        wave1071.wave1061.wave1051.wave1041.wave1031.wave1021.wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )

    def original_handler(
        _renderer: Any,
        _op: object,
        _operands: list[object],
    ) -> None:
        return None

    previous = dispatch.get("W531")
    dispatch["W531"] = original_handler
    try:
        wave1071.test_wave1061_restores_non_empty_previous_handler(caplog, monkeypatch)
        assert dispatch["W531"] is original_handler
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave1061 as wave1061


def _prior_handler(_renderer: Any, _op: object, _operands: list[object]) -> None:
    raise AssertionError("prior handler should be restored")


def test_wave1061_sentinel_handler_is_exercisable() -> None:
    with pytest.raises(AssertionError, match="sentinel handler should be restored"):
        wave1061._sentinel_handler(None, object(), [])  # noqa: SLF001


def test_wave1061_restores_non_empty_previous_handler(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatch = (
        wave1061.wave1051.wave1041.wave1031.wave1021.wave1011.wave1001.wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH
    )
    original = dispatch.get("W531")
    dispatch["W531"] = _prior_handler
    try:
        wave1061.test_wave1051_exercises_local_original_handler_and_restores_previous(
            caplog,
            monkeypatch,
        )

        assert dispatch["W531"] is _prior_handler
    finally:
        if original is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = original

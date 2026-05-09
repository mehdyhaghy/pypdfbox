from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave991 as wave991


def test_wave991_exposed_previous_handler_raises() -> None:
    with pytest.raises(AssertionError, match="previous handler should only be restored"):
        wave991._raise_previous_handler(None, object(), [])  # noqa: SLF001


def test_wave991_restores_non_empty_original_handler(
    monkeypatch: pytest.MonkeyPatch,
    caplog: Any,
) -> None:
    def original_handler(
        _renderer: wave991.wave981.wave972.wave966.wave531.PDFRenderer,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise AssertionError("original handler should only be restored")

    dispatch = wave991.wave981.wave972.wave966.wave531.renderer_mod._DISPATCH  # noqa: SLF001
    previous = dispatch.get("W531")
    dispatch["W531"] = original_handler
    try:
        wave991.test_wave981_original_handler_raise_restores_existing_previous(
            monkeypatch,
            caplog,
        )

        assert dispatch["W531"] is original_handler
    finally:
        if previous is None:
            dispatch.pop("W531", None)
        else:
            dispatch["W531"] = previous

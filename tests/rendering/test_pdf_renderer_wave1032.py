from __future__ import annotations

from typing import Any

import pytest

from tests.rendering import test_pdf_renderer_wave922 as wave922


def test_wave922_local_handler_is_invoked(
    caplog: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def call_wave922_handler(_caplog: Any, _monkeypatch: pytest.MonkeyPatch) -> None:
        wave922.wave591.renderer_module._DISPATCH["W591"](None, object(), [])  # noqa: SLF001

    monkeypatch.setattr(
        wave922.wave591,
        "test_process_operator_logs_and_swallows_handler_os_error",
        call_wave922_handler,
    )

    with pytest.raises(
        AssertionError,
        match="original handler should only be restored",
    ):
        wave922.test_wave591_dispatch_restore_else_branch(caplog, monkeypatch)

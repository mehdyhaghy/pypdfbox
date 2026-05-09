from __future__ import annotations

import builtins
from typing import Any

import pytest

from tests.pdmodel.interactive.measurement import test_pd_viewport_dictionary as viewport_tests


def test_measure_round_trip_exercises_importerror_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__
    target = "pypdfbox.pdmodel.interactive.measurement.pd_measure_dictionary"
    blocked_imports_remaining = 2

    def import_with_temporary_measure_gap(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        nonlocal blocked_imports_remaining
        if name == target and blocked_imports_remaining:
            blocked_imports_remaining -= 1
            raise ImportError("forced missing PDMeasureDictionary")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_with_temporary_measure_gap)

    viewport_tests.test_measure_round_trip()
    assert blocked_imports_remaining == 0

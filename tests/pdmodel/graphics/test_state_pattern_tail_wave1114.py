from __future__ import annotations

import pytest

import tests.pdmodel.graphics.test_state_pattern_tail_wave763 as wave763


def test_wave1114_reuses_wave763_import_shim_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def get_group_with_unblocked_import(self: object) -> None:
        import math  # noqa: F401

        return None

    monkeypatch.setattr(wave763.PDSoftMask, "get_group", get_group_with_unblocked_import)

    wave763.test_soft_mask_get_group_returns_none_when_import_fails(monkeypatch)

from __future__ import annotations

import pytest

import tests.pdmodel.graphics.test_state_pattern_tail_wave763 as wave763


def test_wave1114_reuses_wave763_import_failure_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wave763.test_soft_mask_get_group_propagates_import_failure(monkeypatch)

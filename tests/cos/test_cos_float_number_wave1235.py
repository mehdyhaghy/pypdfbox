from __future__ import annotations

import pytest

from tests.cos import test_cos_float_number_wave1227 as wave1227


def test_wave1235_find_nested_code_raises_for_missing_name() -> None:
    with pytest.raises(AssertionError, match="missing_nested not found"):
        wave1227._find_nested_code(
            wave1227.test_wave1227_wave699_number_accept_helper_returns_visitor.__code__,
            "missing_nested",
        )

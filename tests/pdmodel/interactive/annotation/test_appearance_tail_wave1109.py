from __future__ import annotations

from tests.pdmodel.interactive.annotation.test_appearance_tail_wave766 import (
    _NegativeModuloInt,
)


def test_wave1109_negative_modulo_helper_uses_int_modulo_fallback() -> None:
    assert _NegativeModuloInt(5) % 2 == 1

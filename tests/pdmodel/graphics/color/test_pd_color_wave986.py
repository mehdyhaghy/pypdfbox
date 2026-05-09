from __future__ import annotations

from tests.pdmodel.graphics.color.test_pd_color_wave468 import (
    _BadUnderlyingCountColorSpace,
    _UnderlyingRaisesColorSpace,
)


def test_wave986_pattern_helper_names_are_exercised() -> None:
    assert _UnderlyingRaisesColorSpace().get_name() == "Pattern"
    assert _BadUnderlyingCountColorSpace().get_name() == "Pattern"

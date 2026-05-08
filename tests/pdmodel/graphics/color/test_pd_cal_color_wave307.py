from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor


def test_pd_color_cal_gray_uses_calibrated_converter() -> None:
    cs = PDCalGray()
    cs.set_gamma(2.0)

    components = [0.5]

    assert PDColor(components, cs).to_rgb() == pytest.approx(cs.to_rgb(components))
    assert PDColor(components, cs).to_rgb() != pytest.approx((0.5, 0.5, 0.5))


def test_pd_color_cal_rgb_uses_calibrated_converter() -> None:
    cs = PDCalRGB()
    cs.set_gamma([2.0, 1.0, 1.0])
    cs.set_matrix([0.6, 0.2, 0.0, 0.1, 0.7, 0.2, 0.0, 0.1, 0.8])

    components = [0.5, 0.25, 0.75]

    assert PDColor(components, cs).to_rgb() == pytest.approx(cs.to_rgb(components))
    assert PDColor(components, cs).to_rgb() != pytest.approx(tuple(components))

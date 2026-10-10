"""Ported from upstream ``PDCalGrayTest.java`` (PDFBox 3.0 branch, added by
PDFBOX-6260 for the unreleased 3.0.9).

Tests the calibration of CalGray. A neutral gray must only depend on the
gamma, not on the whitepoint the space is declared relative to. Upstream's
``PDTristimulus`` whitepoint maps to pypdfbox's flat ``list[float]``
``set_white_point``.
"""

import pytest

from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray

WHITEPOINTS = [
    [1.0, 1.0, 1.0],
    [0.9642, 1.0, 0.8249],  # D50
    [0.9505, 1.0, 1.089],  # D65
    [0.95045, 1.0, 1.08905],  # D65, more precise
]


def _create(whitepoint: list[float], gamma: float) -> PDCalGray:
    cal_gray = PDCalGray()
    cal_gray.set_white_point(whitepoint)
    cal_gray.set_gamma(gamma)
    return cal_gray


@pytest.mark.parametrize("whitepoint", WHITEPOINTS)
def test_white_and_black(whitepoint: list[float]) -> None:
    """PDFBOX-2971 and PDFBOX-6260: white and black must stay white and
    black for every whitepoint (white was once rendered as cyan because the
    whitepoint wasn't adapted)."""
    cal_gray = _create(whitepoint, 2.2)
    for i in range(3):
        assert cal_gray.to_rgb([1.0])[i] == pytest.approx(1.0, abs=0.01)
        assert cal_gray.to_rgb([0.0])[i] == pytest.approx(0.0, abs=0.01)


@pytest.mark.parametrize("gamma", [1.0, 1.8, 2.2, 3.0])
def test_independent_of_whitepoint(gamma: float) -> None:
    """A gray must be neutral and must not depend on the whitepoint, only
    on the gamma."""
    reference = _create(WHITEPOINTS[0], gamma).to_rgb([0.5])
    for whitepoint in WHITEPOINTS:
        rgb = _create(whitepoint, gamma).to_rgb([0.5])
        for i in range(3):
            assert rgb[i] == pytest.approx(rgb[0], abs=0.01), (
                f"not neutral, gamma {gamma}"
            )
            assert rgb[i] == pytest.approx(reference[i], abs=0.01), f"gamma {gamma}"


@pytest.mark.parametrize("whitepoint", WHITEPOINTS)
def test_gamma(whitepoint: list[float]) -> None:
    """The gamma must be applied also for a whitepoint other than (1 1 1);
    before, it was ignored. The expected values are the sRGB encoding of
    the linear value 0.5^gamma."""
    # linear value 0.5 is 0.735 in sRGB
    assert _create(whitepoint, 1.0).to_rgb([0.5])[0] == pytest.approx(0.735, abs=0.01)
    # gamma 2.2 is close to the sRGB curve, so the value stays about the same
    assert _create(whitepoint, 2.2).to_rgb([0.5])[0] == pytest.approx(0.5, abs=0.02)

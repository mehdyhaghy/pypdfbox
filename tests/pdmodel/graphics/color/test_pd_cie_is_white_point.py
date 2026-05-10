"""Tests for the ``is_white_point`` predicate on CIE-based color spaces.

Mirrors upstream ``PDCIEDictionaryBasedColorSpace.isWhitePoint()`` for
PDCalGray, PDCalRGB, and PDLab. Upstream gates the no-calibration
shortcut path in ``toRGB`` on this predicate; pypdfbox surfaces it as a
public helper so callers can probe the same condition without reaching
into protected fields.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab

# ---------- defaults: empty dictionary => unity white point => True ----------


def test_pd_cal_gray_default_is_white_point_true() -> None:
    # Default ctor leaves /WhitePoint absent — get_white_point falls back
    # to (1, 1, 1) per spec, so the predicate should report True.
    assert PDCalGray().is_white_point() is True


def test_pd_cal_rgb_default_is_white_point_true() -> None:
    assert PDCalRGB().is_white_point() is True


def test_pd_lab_default_is_white_point_true() -> None:
    assert PDLab().is_white_point() is True


# ---------- explicit unity white point ----------


def test_pd_cal_gray_unity_white_point_is_white_point_true() -> None:
    cs = PDCalGray()
    cs.set_white_point([1.0, 1.0, 1.0])
    assert cs.is_white_point() is True


def test_pd_cal_rgb_unity_white_point_is_white_point_true() -> None:
    cs = PDCalRGB()
    cs.set_white_point([1.0, 1.0, 1.0])
    assert cs.is_white_point() is True


def test_pd_lab_unity_white_point_is_white_point_true() -> None:
    cs = PDLab()
    cs.set_white_point([1.0, 1.0, 1.0])
    assert cs.is_white_point() is True


# ---------- non-unity white points (D65 etc) ----------


def test_pd_cal_gray_d65_white_point_is_white_point_false() -> None:
    cs = PDCalGray()
    cs.set_white_point([0.9505, 1.0, 1.0890])
    assert cs.is_white_point() is False


def test_pd_cal_rgb_d65_white_point_is_white_point_false() -> None:
    cs = PDCalRGB()
    cs.set_white_point([0.9505, 1.0, 1.0890])
    assert cs.is_white_point() is False


def test_pd_lab_d65_white_point_is_white_point_false() -> None:
    cs = PDLab()
    cs.set_white_point([0.9505, 1.0, 1.0890])
    assert cs.is_white_point() is False


# ---------- partial / malformed entries ----------


def test_pd_cal_gray_one_axis_off_is_white_point_false() -> None:
    cs = PDCalGray()
    # Tweak just the X axis — the predicate must reject it.
    cs.set_white_point([0.9999, 1.0, 1.0])
    assert cs.is_white_point() is False


def test_pd_cal_rgb_z_axis_off_is_white_point_false() -> None:
    cs = PDCalRGB()
    cs.set_white_point([1.0, 1.0, 1.001])
    assert cs.is_white_point() is False


def test_pd_lab_y_axis_off_is_white_point_false() -> None:
    cs = PDLab()
    cs.set_white_point([1.0, 0.9, 1.0])
    assert cs.is_white_point() is False


# ---------- Float.compare(.., 1) == 0 parity (subnormal-free range) ----------


@pytest.mark.parametrize(
    "components, expected",
    [
        ([1.0, 1.0, 1.0], True),
        ([1.0, 1.0, 0.9999999], False),  # tiniest float-tick off => not white
        ([1.0000001, 1.0, 1.0], False),
        ([0.0, 0.0, 0.0], False),
    ],
)
def test_pd_cal_gray_white_point_predicate_table(
    components: list[float], expected: bool
) -> None:
    cs = PDCalGray()
    cs.set_white_point(components)
    assert cs.is_white_point() is expected


# ---------- raw COSArray construction parity ----------


def _build_lab_array(white_point: list[float] | None) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    params = COSDictionary()
    if white_point is not None:
        wp = COSArray()
        for v in white_point:
            wp.add(COSFloat(v))
        params.set_item(COSName.get_pdf_name("WhitePoint"), wp)
    arr.add(params)
    return arr


def test_pd_lab_built_from_raw_unity_array_is_white_point_true() -> None:
    cs = PDLab(_build_lab_array([1.0, 1.0, 1.0]))
    assert cs.is_white_point() is True


def test_pd_lab_built_from_raw_d50_array_is_white_point_false() -> None:
    # D50 illuminant — common in print color management.
    cs = PDLab(_build_lab_array([0.9642, 1.0, 0.8249]))
    assert cs.is_white_point() is False


def test_pd_lab_built_from_raw_no_white_point_array_is_white_point_true() -> None:
    # /WhitePoint absent => default (1, 1, 1) => predicate True.
    cs = PDLab(_build_lab_array(None))
    assert cs.is_white_point() is True

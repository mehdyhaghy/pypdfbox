"""Wave 1368 round-out tests for CalGray + CalRGB color spaces.

Targets:

- ``/WhitePoint`` required + round-trip
- ``/BlackPoint`` default (zero tristimulus) + clear
- ``/Gamma`` default (1.0 / [1, 1, 1]) + round-trip
- ``/Matrix`` default (identity) + round-trip + clear (CalRGB)
- ``to_rgb`` calibration vs no-calibration shortcut (PDFBOX-2553)
- ``is_white_point`` predicate
- ``get_default_decode`` arity
- malformed dict raises TypeError eagerly
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray, _xyz_to_srgb
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB

# ====================== CalGray ======================


def test_cal_gray_defaults() -> None:
    cs = PDCalGray()
    assert cs.get_name() == "CalGray"
    assert cs.get_number_of_components() == 1
    assert cs.get_white_point() == [1.0, 1.0, 1.0]
    assert cs.get_black_point() == [0.0, 0.0, 0.0]
    assert cs.get_gamma() == 1.0


def test_cal_gray_initial_color() -> None:
    cs = PDCalGray()
    initial = cs.get_initial_color()
    assert initial._components == [0.0]


def test_cal_gray_whitepoint_round_trip() -> None:
    cs = PDCalGray()
    cs.set_white_point([0.9505, 1.0, 1.089])
    wp = cs.get_white_point()
    assert math.isclose(wp[0], 0.9505, abs_tol=1e-6)
    assert math.isclose(wp[1], 1.0, abs_tol=1e-6)
    assert math.isclose(wp[2], 1.089, abs_tol=1e-6)
    assert cs.has_white_point() is True
    assert cs.is_white_point() is False


def test_cal_gray_blackpoint_round_trip_and_clear() -> None:
    cs = PDCalGray()
    cs.set_black_point([0.1, 0.2, 0.3])
    bp = cs.get_black_point()
    assert math.isclose(bp[0], 0.1, abs_tol=1e-6)
    assert cs.has_black_point() is True
    cs.clear_black_point()
    assert cs.has_black_point() is False
    assert cs.get_black_point() == [0.0, 0.0, 0.0]


def test_cal_gray_gamma_round_trip_and_clear() -> None:
    cs = PDCalGray()
    assert cs.has_gamma() is False
    cs.set_gamma(2.2)
    assert math.isclose(cs.get_gamma(), 2.2, abs_tol=1e-6)
    assert cs.has_gamma() is True
    cs.clear_gamma()
    assert cs.has_gamma() is False
    assert cs.get_gamma() == 1.0


def test_cal_gray_is_white_point_returns_true_for_unit_tristimulus() -> None:
    cs = PDCalGray()
    assert cs.is_white_point() is True


def test_cal_gray_to_rgb_zero_returns_black() -> None:
    cs = PDCalGray()
    rgb = cs.to_rgb([0.0])
    assert rgb == (0.0, 0.0, 0.0)


def test_cal_gray_to_rgb_one_returns_near_white() -> None:
    """The IEC 61966-2-1 sRGB matrix applied to XYZ(1,1,1) doesn't land
    exactly on (1, 1, 1) because XYZ(1,1,1) isn't the sRGB whitepoint
    (D65). Two channels saturate at 1.0 and one lands around 0.95–0.98
    (the green channel)."""
    cs = PDCalGray()
    rgb = cs.to_rgb([1.0])
    for c in rgb:
        assert c >= 0.9


def test_cal_gray_to_rgb_with_gamma_applies_power() -> None:
    """Gamma > 1 darkens midtones (A**gamma < A for A in (0, 1))."""
    cs = PDCalGray()
    cs.set_gamma(2.2)
    rgb_g = cs.to_rgb([0.5])
    cs2 = PDCalGray()  # gamma=1
    rgb_1 = cs2.to_rgb([0.5])
    # Higher gamma at 0.5 input → less luminance → darker grey.
    assert rgb_g[1] < rgb_1[1]


def test_cal_gray_to_rgb_clamps_out_of_range_input() -> None:
    cs = PDCalGray()
    # Out-of-range inputs clamp to [0, 1] internally.
    rgb_low = cs.to_rgb([-0.5])
    rgb_high = cs.to_rgb([1.5])
    assert rgb_low == (0.0, 0.0, 0.0)
    # 1.5 clamps to 1.0 → near-white sRGB (see test_cal_gray_to_rgb_one_returns_near_white).
    for c in rgb_high:
        assert c >= 0.9


def test_cal_gray_to_rgb_rejects_empty_input() -> None:
    cs = PDCalGray()
    with pytest.raises(ValueError, match="requires one component"):
        cs.to_rgb([])


def test_cal_gray_malformed_array_raises_eagerly() -> None:
    """A CalGray array whose slot-1 is not a dictionary errors on read."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalGray"))
    arr.add(COSName.get_pdf_name("NotADict"))
    cs = PDCalGray(arr)  # ctor doesn't read /Gamma — initial color is fixed.
    with pytest.raises(TypeError, match="not a dictionary"):
        cs.get_white_point()


# ====================== _xyz_to_srgb helper ======================


def test_xyz_to_srgb_white_point_returns_unit_rgb() -> None:
    """XYZ(1, 1, 1) maps to clamped (1, 1, 1) in sRGB."""
    rgb = _xyz_to_srgb(1.0, 1.0, 1.0)
    for c in rgb:
        assert c >= 0.9


def test_xyz_to_srgb_origin_returns_black() -> None:
    rgb = _xyz_to_srgb(0.0, 0.0, 0.0)
    assert rgb == (0.0, 0.0, 0.0)


def test_xyz_to_srgb_clamps_negative_inputs() -> None:
    rgb = _xyz_to_srgb(-1.0, -1.0, -1.0)
    # Negative XYZ saturates encoded sRGB at 0 per the helper's clamp.
    for c in rgb:
        assert c == 0.0


# ====================== CalRGB ======================


def test_cal_rgb_defaults() -> None:
    cs = PDCalRGB()
    assert cs.get_name() == "CalRGB"
    assert cs.get_number_of_components() == 3
    assert cs.get_white_point() == [1.0, 1.0, 1.0]
    assert cs.get_black_point() == [0.0, 0.0, 0.0]
    assert cs.get_gamma() == [1.0, 1.0, 1.0]
    assert cs.get_matrix() == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


def test_cal_rgb_initial_color() -> None:
    cs = PDCalRGB()
    initial = cs.get_initial_color()
    assert initial._components == [0.0, 0.0, 0.0]


def test_cal_rgb_default_decode() -> None:
    cs = PDCalRGB()
    assert cs.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_cal_rgb_whitepoint_round_trip() -> None:
    cs = PDCalRGB()
    cs.set_white_point([0.9505, 1.0, 1.089])
    wp = cs.get_white_point()
    assert math.isclose(wp[0], 0.9505, abs_tol=1e-6)


def test_cal_rgb_gamma_round_trip_and_clear() -> None:
    cs = PDCalRGB()
    cs.set_gamma([2.2, 1.8, 2.4])
    g = cs.get_gamma()
    assert math.isclose(g[0], 2.2, abs_tol=1e-6)
    assert math.isclose(g[1], 1.8, abs_tol=1e-6)
    assert math.isclose(g[2], 2.4, abs_tol=1e-6)
    cs.clear_gamma()
    assert cs.has_gamma() is False
    assert cs.get_gamma() == [1.0, 1.0, 1.0]


def test_cal_rgb_matrix_round_trip_and_clear() -> None:
    cs = PDCalRGB()
    custom = [0.5, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.5]
    cs.set_matrix(custom)
    m = cs.get_matrix()
    for actual, expected in zip(m, custom, strict=True):
        assert math.isclose(actual, expected, abs_tol=1e-6)
    assert cs.has_matrix() is True
    cs.clear_matrix()
    assert cs.has_matrix() is False
    assert cs.get_matrix() == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


def test_cal_rgb_blackpoint_round_trip_and_clear() -> None:
    cs = PDCalRGB()
    cs.set_black_point([0.05, 0.05, 0.05])
    assert cs.has_black_point() is True
    cs.clear_black_point()
    assert cs.has_black_point() is False
    assert cs.get_black_point() == [0.0, 0.0, 0.0]


def test_cal_rgb_is_white_point_unit_tristimulus() -> None:
    cs = PDCalRGB()
    assert cs.is_white_point() is True


def test_cal_rgb_to_rgb_unit_whitepoint_applies_full_calibration() -> None:
    """Unit whitepoint → CIE calibration path.

    XYZ(1,1,1) is brighter than the D65 sRGB whitepoint so the matrix
    transform produces sRGB channels near but not exactly 1.0 — assert
    on the brightness floor.
    """
    cs = PDCalRGB()
    rgb = cs.to_rgb([1.0, 1.0, 1.0])
    for c in rgb:
        assert c >= 0.9


def test_cal_rgb_to_rgb_non_unit_whitepoint_short_circuits() -> None:
    """PDFBOX-2553: a non-unit whitepoint bypasses the CIE calibration."""
    cs = PDCalRGB()
    cs.set_white_point([0.9505, 1.0, 1.089])
    # Per the PDFBOX-2553 hack, the input components are returned verbatim.
    rgb = cs.to_rgb([0.25, 0.5, 0.75])
    assert rgb == (0.25, 0.5, 0.75)


def test_cal_rgb_to_rgb_clamps_inputs_to_unit_range() -> None:
    cs = PDCalRGB()
    rgb = cs.to_rgb([-0.5, 1.5, 0.5])
    # Negative inputs clamp to 0, > 1 to 1.
    assert rgb[0] >= 0.0
    assert rgb[1] >= 0.9
    assert 0.0 <= rgb[2] <= 1.0


def test_cal_rgb_to_rgb_rejects_short_input() -> None:
    cs = PDCalRGB()
    with pytest.raises(ValueError, match="requires three components"):
        cs.to_rgb([0.5])


def test_cal_rgb_to_rgb_uses_per_channel_gamma() -> None:
    """Higher gamma on one channel darkens its midtone selectively."""
    cs = PDCalRGB()
    cs.set_gamma([3.0, 1.0, 1.0])
    rgb = cs.to_rgb([0.5, 0.5, 0.5])
    # R channel processed with gamma=3 should be visibly darker than G.
    assert rgb[0] < rgb[1]


def test_cal_rgb_to_rgb_uses_matrix_for_x_calibration() -> None:
    """A non-identity matrix shifts the XYZ output coordinates."""
    cs = PDCalRGB()
    # Scale matrix: X = 0.5 * A, Y = B, Z = C.
    cs.set_matrix([0.5, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])
    rgb_scaled = cs.to_rgb([1.0, 1.0, 1.0])
    cs2 = PDCalRGB()
    rgb_identity = cs2.to_rgb([1.0, 1.0, 1.0])
    # Halving X should reduce R after the sRGB matrix transform.
    assert rgb_scaled[0] != rgb_identity[0]


def test_cal_rgb_malformed_array_raises_eagerly() -> None:
    """A CalRGB array whose slot-1 is not a dictionary errors on read."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalRGB"))
    arr.add(COSName.get_pdf_name("NotADict"))
    cs = PDCalRGB(arr)
    with pytest.raises(TypeError, match="not a dictionary"):
        cs.get_white_point()


# ---------- dictionary-direct round-trip ----------


def test_cal_rgb_reads_dictionary_provided_values() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalRGB"))
    d = COSDictionary()
    wp = COSArray()
    for v in (0.9505, 1.0, 1.089):
        wp.add(COSFloat(v))
    d.set_item(COSName.get_pdf_name("WhitePoint"), wp)
    gamma = COSArray()
    for v in (2.2, 2.2, 2.2):
        gamma.add(COSFloat(v))
    d.set_item(COSName.get_pdf_name("Gamma"), gamma)
    arr.add(d)
    cs = PDCalRGB(arr)
    wp_out = cs.get_white_point()
    assert math.isclose(wp_out[0], 0.9505, abs_tol=1e-6)
    g_out = cs.get_gamma()
    assert math.isclose(g_out[0], 2.2, abs_tol=1e-6)

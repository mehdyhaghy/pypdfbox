"""Hand-written tests for the color-space fixes forward-ported from the
upstream PDFBox 3.0 branch (unreleased 3.0.9): PDFBOX-5074 (DeviceN spot
colorant not white at zero tint), PDFBOX-5079 (CalRGB D65 tolerance),
PDFBOX-6260 (Bradford chromatic adaptation of the whitepoint) and
PDFBOX-6258 / PDFBOX-6264 (color clamping, Lab range cache).

Numeric expectations are derived from the upstream algorithm: Bradford
adaptation of the declared whitepoint, then XYZ to sRGB.
"""

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_cie_dictionary_based_color_space import (
    PCS_WHITE_D50,
    PCS_WHITE_D65,
    PDCIEDictionaryBasedColorSpace,
    adaptation_matrix,
    xyz_to_srgb_adapted,
)
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
)
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_tristimulus import PDTristimulus

D50 = [0.9642, 1.0, 0.8249]
# Whitepoint from the PDFBOX-6260 report: white rendered as cyan before.
CYAN_CAST_WP = [0.5505, 1.0, 1.989]
# sRGB primaries adapted to D50 (column layout [Xa Ya Za Xb Yb Zb Xc Yc Zc]).
SRGB_D50_MATRIX = [
    0.4360747, 0.2225045, 0.0139322,
    0.3850649, 0.7168786, 0.0971045,
    0.1430804, 0.0606169, 0.7141733,
]


# ---------- PDFBOX-6260: Bradford adaptation ----------


def test_bradford_d65_to_d50_matches_published_matrix() -> None:
    # The well-known Bradford D65 -> D50 matrix (Lindbloom).
    m = adaptation_matrix(0.95047, 1.0, 1.08883, (0.96422, 1.0, 0.82521))
    expected = [
        [1.0478112, 0.0228866, -0.0501270],
        [0.0295424, 0.9904844, -0.0170491],
        [-0.0092345, 0.0150436, 0.7521316],
    ]
    for row, exp_row in zip(m, expected, strict=True):
        assert list(row) == pytest.approx(exp_row, abs=1e-6)


def test_adaptation_maps_source_white_to_destination_white() -> None:
    for wp in ([1.0, 1.0, 1.0], D50, CYAN_CAST_WP):
        m = adaptation_matrix(*wp, PCS_WHITE_D50)
        adapted = [sum(m[i][j] * wp[j] for j in range(3)) for i in range(3)]
        assert adapted == pytest.approx(list(PCS_WHITE_D50), abs=1e-12)


def test_unit_whitepoint_to_d50_matrix_values() -> None:
    m = adaptation_matrix(1.0, 1.0, 1.0, PCS_WHITE_D50)
    assert m[0] == pytest.approx((0.99778129, -0.00415215, -0.02942914), abs=1e-7)
    assert m[1] == pytest.approx((-0.00975731, 1.01832475, -0.00856745), abs=1e-7)
    assert m[2] == pytest.approx((-0.00742934, 0.01346304, 0.81886630), abs=1e-7)


def test_destination_d65_white_is_the_srgb_matrix_white() -> None:
    assert pytest.approx((0.95047, 1.0, 1.08883), abs=1e-5) == PCS_WHITE_D65
    assert xyz_to_srgb_adapted(PCS_WHITE_D65, *PCS_WHITE_D65) == pytest.approx(
        (1.0, 1.0, 1.0), abs=1e-9
    )


def test_degenerate_whitepoint_uses_identity() -> None:
    m = adaptation_matrix(0.0, 0.0, 0.0)
    assert m == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


@pytest.mark.parametrize("wp", [[1.0, 1.0, 1.0], D50, CYAN_CAST_WP])
def test_whitepoint_xyz_converts_to_white(wp: list[float]) -> None:
    assert xyz_to_srgb_adapted(wp, *wp) == pytest.approx((1.0, 1.0, 1.0), abs=1e-9)


def test_negative_adapted_xyz_is_clamped() -> None:
    assert xyz_to_srgb_adapted(D50, -1.0, -1.0, -1.0) == (0.0, 0.0, 0.0)


class _Concrete(PDCIEDictionaryBasedColorSpace):
    def get_name(self) -> str:
        return "CalGray"

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self):  # type: ignore[override]
        return None

    def to_rgb(self, value):  # type: ignore[override]
        return None


def test_cie_dictionary_conv_xyz_uses_cached_whitepoint() -> None:
    cs = _Concrete(COSName.get_pdf_name("CalGray"))
    wp = COSArray()
    for v in CYAN_CAST_WP:
        wp.add(COSFloat(v))
    cs.set_white_point(PDTristimulus(wp))
    assert cs.conv_xy_zto_rgb(*CYAN_CAST_WP) == pytest.approx(
        [1.0, 1.0, 1.0], abs=1e-6
    )


def test_cal_gray_cyan_cast_whitepoint_stays_neutral() -> None:
    # Gamma 1: linear 0.5 encodes to 0.73536 in sRGB, for any whitepoint.
    cs = PDCalGray()
    cs.set_white_point(CYAN_CAST_WP)
    assert cs.to_rgb([1.0]) == pytest.approx((1.0, 1.0, 1.0), abs=1e-9)
    assert cs.to_rgb([0.5]) == pytest.approx((0.735357, 0.735357, 0.735357), abs=1e-6)


def test_cal_gray_applies_gamma_for_non_unit_whitepoint() -> None:
    # Before PDFBOX-6260 a D50 whitepoint returned (A, A, A), ignoring the gamma.
    cs = PDCalGray()
    cs.set_white_point(D50)
    cs.set_gamma(2.0)
    # 0.5^2 = 0.25 linear -> sRGB 0.537099
    assert cs.to_rgb([0.5]) == pytest.approx((0.537099, 0.537099, 0.537099), abs=1e-5)


@pytest.mark.parametrize("wp", [D50, CYAN_CAST_WP, [0.9505, 1.0, 1.089]])
def test_lab_neutral_gray_is_whitepoint_independent(wp: list[float]) -> None:
    cs = PDLab()
    cs.set_white_point(wp)
    assert cs.to_rgb([100.0, 0.0, 0.0]) == pytest.approx((1.0, 1.0, 1.0), abs=1e-9)
    # L* = 50 -> Y = ((50 + 16) / 116)^3 = 0.184186 -> sRGB 0.466327
    assert cs.to_rgb([50.0, 0.0, 0.0]) == pytest.approx(
        (0.466327, 0.466327, 0.466327), abs=1e-6
    )


# ---------- PDFBOX-5079: CalRGB D65 tolerance ----------


@pytest.mark.parametrize(
    ("wp", "expected"),
    [
        ([0.9505, 1.0, 1.089], True),
        ([0.95045, 1.0, 1.08905], True),
        ([0.951, 1.0, 1.089], True),
        ([0.95047, 1.0, 1.08883], True),
        ([0.9643, 1.0, 0.8251], False),  # D50
        ([1.0, 1.0, 1.0], False),
        ([0.961, 1.0, 1.089], False),  # outside the 0.01 tolerance on X
        ([0.9595, 1.0, 1.089], True),  # inside the 0.01 tolerance on X
    ],
)
def test_cal_rgb_is_d65_white_point(wp: list[float], expected: bool) -> None:
    cs = PDCalRGB()
    cs.set_white_point(wp)
    assert cs.is_d65_white_point() is expected


def test_cal_rgb_d65_rounding_skips_calibration() -> None:
    cs = PDCalRGB()
    cs.set_white_point([0.95045, 1.0, 1.08905])
    cs.set_gamma([2.2, 2.2, 2.2])
    assert cs.to_rgb([0.2, 0.4, 0.6]) == (0.2, 0.4, 0.6)


def test_cal_rgb_d50_is_calibrated_to_red() -> None:
    # The PDFBOX-5079 case: a D50 CalRGB space with sRGB primaries renders
    # red as red (it used to take the D65 shortcut).
    cs = PDCalRGB()
    cs.set_white_point(D50)
    cs.set_matrix(SRGB_D50_MATRIX)
    assert cs.to_rgb([1.0, 0.0, 0.0]) == pytest.approx((1.0, 0.0, 0.0), abs=2e-4)
    assert cs.to_rgb([1.0, 1.0, 1.0]) == pytest.approx((1.0, 1.0, 1.0), abs=1e-4)
    assert cs.to_rgb([0.5, 0.5, 0.5]) == pytest.approx(
        (0.735357, 0.735357, 0.735357), abs=5e-4
    )


def test_cal_rgb_unit_whitepoint_white_is_adapted_to_white() -> None:
    # With the identity matrix and whitepoint (1 1 1), XYZ (1 1 1) is the
    # whitepoint itself and now adapts to sRGB white (no color cast).
    cs = PDCalRGB()
    assert cs.to_rgb([1.0, 1.0, 1.0]) == pytest.approx((1.0, 1.0, 1.0), abs=1e-9)


# ---------- PDFBOX-6258 / PDFBOX-6264: clamp + Lab range cache ----------


def test_base_clamp_is_unit_interval() -> None:
    values = [-0.5, 0.0, 0.25, 1.0, 1.5]
    PDDeviceGray.INSTANCE.clamp(values)
    assert values == [0.0, 0.0, 0.25, 1.0, 1.0]


def test_lab_range_cache_follows_range_changes() -> None:
    array = COSArray()
    array.add(COSName.get_pdf_name("Lab"))
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Range"), COSArray.of_cos_floats([-10, 20, -30, 40]))
    array.add(d)
    lab = PDLab(array)
    values = [150.0, 25.0, -35.0]
    lab.clamp(values)
    assert values == [100.0, 20.0, -30.0]
    assert lab.get_default_decode(8) == [0.0, 100.0, -10.0, 20.0, -30.0, 40.0]

    lab.set_range([-1.0, 1.0, -2.0, 2.0])
    values = [-5.0, 5.0, -5.0]
    lab.clamp(values)
    assert values == [0.0, 1.0, -2.0]

    lab.clear_range()
    values = [50.0, 150.0, -150.0]
    lab.clamp(values)
    assert values == [50.0, 100.0, -100.0]
    assert lab.get_default_decode(8) == [0.0, 100.0, -100.0, 100.0, -100.0, 100.0]


# ---------- PDFBOX-5074: DeviceN attributes vs tint transform ----------


def _type2(c0: list[float], c1: list[float]) -> COSDictionary:
    f = COSDictionary()
    f.set_int(COSName.get_pdf_name("FunctionType"), 2)
    f.set_item(COSName.get_pdf_name("Domain"), COSArray.of_cos_floats([0, 1]))
    f.set_item(COSName.get_pdf_name("C0"), COSArray.of_cos_floats(c0))
    f.set_item(COSName.get_pdf_name("C1"), COSArray.of_cos_floats(c1))
    f.set_int(COSName.get_pdf_name("N"), 1)
    return f


def _device_n(spot: COSArray | COSName) -> PDDeviceN:
    colorants = COSDictionary()
    colorants.set_item(COSName.get_pdf_name("Spot"), spot)
    attributes = COSDictionary()
    attributes.set_item(COSName.get_pdf_name("Colorants"), colorants)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray.of_cos_names(["Spot"]))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    # tint transform: red ramp, so it is obvious which path was taken
    arr.add(_type2([1, 1, 1], [1, 0, 0]))
    arr.add(attributes)
    return PDDeviceN(arr)


def _separation(at_zero: list[float], at_one: list[float]) -> COSArray:
    sep = COSArray()
    sep.add(COSName.get_pdf_name("Separation"))
    sep.add(COSName.get_pdf_name("Spot"))
    sep.add(COSName.get_pdf_name("DeviceRGB"))
    sep.add(_type2(at_zero, at_one))
    return sep


def test_white_threshold_boundary_uses_attributes() -> None:
    # RGB 0.9 at zero tint is not below the threshold: still "white".
    device_n = _device_n(_separation([0.9, 0.9, 0.9], [0, 0, 1]))
    assert device_n.use_attributes() is True
    # attributes: 0.9 + 0.5 * (target - 0.9)
    assert device_n.to_rgb([0.5]) == pytest.approx((0.45, 0.45, 0.95), abs=1e-6)


def test_below_white_threshold_uses_tint_transform() -> None:
    device_n = _device_n(_separation([0.89, 1, 1], [0, 0, 1]))
    assert device_n.use_attributes() is False
    # tint transform: 1 + 0.5 * (target - 1) for (1, 0, 0)
    assert device_n.to_rgb([0.5]) == pytest.approx((1.0, 0.5, 0.5), abs=1e-6)


def test_non_separation_spot_colorant_is_checked_too() -> None:
    # DeviceGray at tint 0 is black, so the attributes can't be used.
    device_n = _device_n(COSName.get_pdf_name("DeviceGray"))
    assert device_n.use_attributes() is False
    assert device_n.to_rgb([0.0]) == pytest.approx((1.0, 1.0, 1.0), abs=1e-6)


def test_use_attributes_is_reset_by_set_attributes() -> None:
    device_n = _device_n(_separation([0, 0, 0], [0, 0, 1]))
    assert device_n.use_attributes() is False
    colorants = COSDictionary()
    colorants.set_item(
        COSName.get_pdf_name("Spot"), _separation([1, 1, 1], [0, 0, 1])
    )
    attributes = COSDictionary()
    attributes.set_item(COSName.get_pdf_name("Colorants"), colorants)
    device_n.set_attributes(PDDeviceNAttributes(attributes))
    device_n.init_color_conversion_cache()
    assert device_n.use_attributes() is True
    device_n.set_attributes(None)
    assert device_n.use_attributes() is False

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation


# ---------- Type 2 tint transform builder ----------


def _make_type2_function(
    c0: list[float],
    c1: list[float],
    n: float = 1.0,
    domain: list[float] | None = None,
    range_: list[float] | None = None,
) -> COSDictionary:
    """Build a /FunctionType 2 (exponential interpolation) dictionary."""
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("FunctionType"), 2)
    if domain is None:
        domain = [0.0, 1.0]
    d.set_item(COSName.get_pdf_name("Domain"), COSArray.of_cos_floats(domain))
    if range_ is not None:
        d.set_item(COSName.get_pdf_name("Range"), COSArray.of_cos_floats(range_))
    d.set_item(COSName.get_pdf_name("C0"), COSArray.of_cos_floats(c0))
    d.set_item(COSName.get_pdf_name("C1"), COSArray.of_cos_floats(c1))
    d.set_item(COSName.get_pdf_name("N"), COSFloat(n))
    return d


# ---------- ICCBased ----------


def test_icc_based_n3_no_alternate_falls_back_to_device_rgb() -> None:
    """ICCBased with /N=3 and no /Alternate → identity to DeviceRGB."""
    cs = PDICCBased()  # default /N = 3
    assert cs.get_alternate() is None
    rgb = PDColor([0.25, 0.5, 0.75], cs).to_rgb()
    assert rgb == pytest.approx((0.25, 0.5, 0.75), abs=1e-6)


def test_icc_based_n1_no_alternate_falls_back_to_device_gray() -> None:
    """ICCBased with /N=1 and no /Alternate → DeviceGray semantics."""
    cs = PDICCBased()
    cs.set_n(1)
    rgb = PDColor([0.4], cs).to_rgb()
    assert rgb == pytest.approx((0.4, 0.4, 0.4), abs=1e-6)


def test_icc_based_n4_no_alternate_falls_back_to_device_cmyk() -> None:
    """ICCBased with /N=4 and no /Alternate → DeviceCMYK semantics."""
    cs = PDICCBased()
    cs.set_n(4)
    # Pure red in CMYK: C=0, M=1, Y=1, K=0
    rgb = PDColor([0.0, 1.0, 1.0, 0.0], cs).to_rgb()
    assert rgb[0] == pytest.approx(1.0, abs=1e-6)
    assert rgb[1] == pytest.approx(0.0, abs=1e-6)
    assert rgb[2] == pytest.approx(0.0, abs=1e-6)


def test_icc_based_explicit_alternate_device_cmyk() -> None:
    """ICCBased with explicit /Alternate /DeviceCMYK uses that path."""
    cs = PDICCBased()
    cs.set_n(4)
    cs.set_alternate(PDDeviceCMYK.INSTANCE)
    # Pure black via K only
    rgb = PDColor([0.0, 0.0, 0.0, 1.0], cs).to_rgb()
    assert rgb == (0.0, 0.0, 0.0)


def test_icc_based_unknown_n_returns_none_raises() -> None:
    """ICCBased with /N not in {1,3,4} and no /Alternate → not convertible."""
    cs = PDICCBased()
    cs.set_n(7)
    with pytest.raises(NotImplementedError):
        PDColor([0.0] * 7, cs).to_rgb()


# ---------- Separation ----------


def _build_separation(
    tint_transform: COSDictionary,
    alternate_name: str = "DeviceRGB",
) -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("MyColorant"))
    arr.add(COSName.get_pdf_name(alternate_name))
    arr.add(tint_transform)
    return PDSeparation(arr)


def test_separation_type2_red_at_full_tint() -> None:
    """Separation with TintTransform (Type 2) {0,0,0}->{1,0,0} maps
    full tint to pure red in DeviceRGB."""
    func = _make_type2_function([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    cs = _build_separation(func)
    rgb = PDColor([1.0], cs).to_rgb()
    assert rgb == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)


def test_separation_type2_red_at_half_tint() -> None:
    """At tint=0.5 the linear interpolation gives mid-red."""
    func = _make_type2_function([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    cs = _build_separation(func)
    rgb = PDColor([0.5], cs).to_rgb()
    assert rgb == pytest.approx((0.5, 0.0, 0.0), abs=1e-6)


def test_separation_type2_zero_tint_is_white() -> None:
    """At tint=0 the function returns C0 → black components in this map."""
    func = _make_type2_function([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    cs = _build_separation(func)
    rgb = PDColor([0.0], cs).to_rgb()
    assert rgb == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


# ---------- DeviceN ----------


def _build_device_n(
    colorants: list[str],
    tint_transform: COSDictionary,
    alternate_name: str = "DeviceRGB",
) -> PDDeviceN:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray.of_cos_names(colorants))
    arr.add(COSName.get_pdf_name(alternate_name))
    arr.add(tint_transform)
    return PDDeviceN(arr)


def test_device_n_two_component_identity_first_channel() -> None:
    """DeviceN with 2 colorants. Type 2 tint transform takes input[0]
    (Type 2 always uses a single input) and maps it to a 3-vector. We
    pick a transform that sends t -> (t, 0, 0) so the first colorant
    drives the red channel."""
    func = _make_type2_function([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    cs = _build_device_n(["Red", "Green"], func)
    rgb = PDColor([0.7, 0.2], cs).to_rgb()
    # input[0] = 0.7 → (0.7, 0, 0); input[1] is ignored by Type 2
    assert rgb == pytest.approx((0.7, 0.0, 0.0), abs=1e-6)


def test_device_n_alternate_device_cmyk() -> None:
    """DeviceN with alternate /DeviceCMYK. Tint transform maps to a
    4-vector representing CMYK pure black via K."""
    func = _make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])
    cs = _build_device_n(["Black"], func, alternate_name="DeviceCMYK")
    rgb = PDColor([1.0], cs).to_rgb()
    assert rgb == (0.0, 0.0, 0.0)


# ---------- Pattern ----------


def test_uncolored_pattern_with_underlying_device_rgb() -> None:
    """Uncolored tiling pattern: underlying color space is DeviceRGB,
    components carry the paint color. Result is the underlying color's
    to_rgb."""
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    color = PDColor([0.2, 0.4, 0.8], cs, COSName.get_pdf_name("P1"))
    rgb = color.to_rgb()
    assert rgb == pytest.approx((0.2, 0.4, 0.8), abs=1e-6)


def test_uncolored_pattern_with_underlying_device_gray() -> None:
    cs = PDPattern(PDDeviceGray.INSTANCE)
    color = PDColor([0.6], cs, COSName.get_pdf_name("P2"))
    rgb = color.to_rgb()
    assert rgb == pytest.approx((0.6, 0.6, 0.6), abs=1e-6)


def test_colored_pattern_no_underlying_raises() -> None:
    """Colored tiling pattern (no underlying CS) cannot resolve to
    sRGB without rendering — raises NotImplementedError."""
    cs = PDPattern()  # no underlying
    color = PDColor([], cs, COSName.get_pdf_name("P3"))
    with pytest.raises(NotImplementedError):
        color.to_rgb()


# ---------- Cross-cutting: ICCBased -> Alternate -> DeviceCMYK round-trip ----------


def test_icc_based_alternate_round_trip_via_cos_array() -> None:
    """An ICCBased CS reconstructed from a parsed /ICCBased array with
    /Alternate /DeviceCMYK in the stream dict resolves through it."""
    icc_arr = COSArray()
    icc_arr.add(COSName.get_pdf_name("ICCBased"))
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("N"), 4)
    stream.set_item(
        COSName.get_pdf_name("Alternate"), COSName.get_pdf_name("DeviceCMYK")
    )
    icc_arr.add(stream)
    cs = PDICCBased(icc_arr)
    rgb = PDColor([0.0, 0.0, 0.0, 1.0], cs).to_rgb()
    assert rgb == (0.0, 0.0, 0.0)


# ---------- ICCBased + COSInteger /N ----------


def test_icc_based_components_clamped_in_alternate() -> None:
    """Out-of-range components are still clamped by the alternate
    DeviceRGB path."""
    cs = PDICCBased()  # /N = 3
    rgb = PDColor([1.5, -0.2, 0.5], cs).to_rgb()
    assert rgb == (1.0, 0.0, 0.5)


# Silence unused import warnings if the file is collected without all paths.
_ = COSInteger

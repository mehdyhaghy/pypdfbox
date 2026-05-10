from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- helpers ----------


def _make_type2_function(
    c0: list[float],
    c1: list[float],
    n: float = 1.0,
    domain: list[float] | None = None,
) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats(domain or [0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _build_separation(
    tint_transform: COSDictionary,
    colorant_name: str = "MyColorant",
    alternate_name: str = "DeviceRGB",
) -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant_name))
    arr.add(COSName.get_pdf_name(alternate_name))
    arr.add(tint_transform)
    return PDSeparation(arr)


# ---------- get_colorant_name ----------


def test_get_colorant_name_round_trip() -> None:
    cs = PDSeparation()
    cs.set_colorant_name("PANTONE 185 C")
    assert cs.get_colorant_name() == "PANTONE 185 C"


def test_get_colorant_name_default_ctor_empty() -> None:
    cs = PDSeparation()
    # Default ctor seeds the slot with COSName("")
    assert cs.get_colorant_name() == ""


def test_get_colorant_name_from_cos_array() -> None:
    func = _make_type2_function([0.0], [1.0])
    cs = _build_separation(func, colorant_name="SpotRed")
    assert cs.get_colorant_name() == "SpotRed"


# ---------- get_alternate_color_space ----------


def test_get_alternate_color_space_resolves_named_cmyk() -> None:
    func = _make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0])
    cs = _build_separation(func, alternate_name="DeviceCMYK")
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceCMYK"


def test_set_alternate_color_space_writes_through_to_array() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert arr.get_name(2) == "DeviceRGB"


# ---------- get_tint_transform returns PDFunction ----------


def test_get_tint_transform_returns_pd_function() -> None:
    func = _make_type2_function([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    cs = _build_separation(func)
    fn = cs.get_tint_transform()
    assert isinstance(fn, PDFunction)
    assert fn.get_function_type() == 2


def test_get_tint_transform_none_for_placeholder() -> None:
    """Default-ctor PDSeparation has placeholder names in the tint
    slot — typed accessor returns ``None`` rather than raising."""
    cs = PDSeparation()
    assert cs.get_tint_transform() is None


def test_get_tint_transform_cos_returns_raw_dict() -> None:
    func = _make_type2_function([0.0], [1.0])
    cs = _build_separation(func)
    raw = cs.get_tint_transform_cos()
    assert isinstance(raw, COSDictionary)
    assert raw.get_int("FunctionType") == 2


def test_set_tint_transform_accepts_pd_function() -> None:
    func_dict = _make_type2_function([0.0], [1.0])
    function = PDFunction.create(func_dict)
    cs = PDSeparation()
    cs.set_tint_transform(function)
    raw = cs.get_tint_transform_cos()
    assert raw is function.get_cos_object()


def test_set_tint_transform_accepts_raw_cos() -> None:
    func_dict = _make_type2_function([0.0], [1.0])
    cs = PDSeparation()
    cs.set_tint_transform(func_dict)
    assert cs.get_tint_transform_cos() is func_dict


def test_set_tint_transform_rejects_invalid_type() -> None:
    cs = PDSeparation()
    with pytest.raises(TypeError):
        cs.set_tint_transform(42)  # type: ignore[arg-type]


# ---------- to_rgb integration ----------


def test_separation_to_rgb_via_cmyk_alternate() -> None:
    """Separation called ``SpotRed`` with /DeviceCMYK alternate. Tint
    transform maps tint t -> (0, t, t, 0); at t=1 we get pure CMYK red
    which converts to RGB (1, 0, 0)."""
    func = _make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0])
    cs = _build_separation(func, colorant_name="SpotRed", alternate_name="DeviceCMYK")
    rgb = PDColor([1.0], cs).to_rgb()
    assert rgb == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)


def test_separation_to_rgb_at_half_tint_via_cmyk() -> None:
    """At tint=0.5 the linear (N=1) interpolation yields half-strength
    CMYK red (0, 0.5, 0.5, 0); to RGB that is (0.5, 0.5, 0.5).

    CMYK->RGB: r = (1-c)*(1-k) = (1-0)*(1-0) = 1.0; that's wrong. The
    CMYK->RGB conversion at C=0, M=0.5, Y=0.5, K=0 is:
        r = (1 - 0)   * (1 - 0) = 1.0
        g = (1 - 0.5) * (1 - 0) = 0.5
        b = (1 - 0.5) * (1 - 0) = 0.5
    So the expected RGB is (1.0, 0.5, 0.5) — pink, the natural half-tint
    of red on white paper."""
    func = _make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0])
    cs = _build_separation(func, alternate_name="DeviceCMYK")
    rgb = PDColor([0.5], cs).to_rgb()
    assert rgb == pytest.approx((1.0, 0.5, 0.5), abs=1e-6)


def test_separation_to_rgb_returns_none_without_tint_transform() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    # Tint transform slot is still the default placeholder.
    assert cs.to_rgb([1.0]) is None


def test_separation_to_rgb_returns_none_without_alternate() -> None:
    cs = PDSeparation()
    # No alternate set; the default placeholder is COSName("") which
    # PDColorSpace.create cannot resolve.
    assert cs.to_rgb([1.0]) is None


def test_separation_explicit_setters_round_trip_via_to_rgb() -> None:
    """Set everything via setters and exercise the full to_rgb path
    against a CMYK alternate."""
    cs = PDSeparation()
    cs.set_colorant_name("Black")
    cs.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    func = _make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])
    cs.set_tint_transform(func)
    rgb = cs.to_rgb([1.0])
    assert rgb == (0.0, 0.0, 0.0)

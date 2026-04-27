from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
)
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
    PDDeviceNProcess,
)
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation


# ---------- helpers ----------


def _make_type2_function(
    c0: list[float],
    c1: list[float],
    n: float = 1.0,
    domain: list[float] | None = None,
) -> COSDictionary:
    """Build a /FunctionType 2 (exponential interpolation) dictionary."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats(domain or [0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _build_device_n(
    colorants: list[str],
    tint_transform: COSDictionary,
    alternate_name: str = "DeviceRGB",
    attributes: COSDictionary | None = None,
) -> PDDeviceN:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray.of_cos_names(colorants))
    arr.add(COSName.get_pdf_name(alternate_name))
    arr.add(tint_transform)
    if attributes is not None:
        arr.add(attributes)
    return PDDeviceN(arr)


# ---------- get_colorant_names ----------


def test_get_colorant_names_round_trip() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["Cyan", "Magenta", "Yellow", "Black"])
    assert cs.get_colorant_names() == ["Cyan", "Magenta", "Yellow", "Black"]


def test_get_colorant_names_empty_default_ctor() -> None:
    assert PDDeviceN().get_colorant_names() == []


# ---------- get_alternate_color_space ----------


def test_get_alternate_color_space_resolves_named() -> None:
    func = _make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])
    cs = _build_device_n(["Black"], func, alternate_name="DeviceCMYK")
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceCMYK"


def test_set_alternate_color_space_writes_through_to_array() -> None:
    cs = PDDeviceN()
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    arr = cs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert arr.get_name(2) == "DeviceRGB"


# ---------- get_tint_transform returns PDFunction ----------


def test_get_tint_transform_returns_pd_function() -> None:
    func = _make_type2_function([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    cs = _build_device_n(["Red"], func)
    fn = cs.get_tint_transform()
    assert isinstance(fn, PDFunction)
    assert fn.get_function_type() == 2


def test_get_tint_transform_none_for_placeholder() -> None:
    """A freshly-constructed PDDeviceN holds a COSName placeholder in the
    tint transform slot — the typed accessor returns ``None`` rather
    than raising."""
    cs = PDDeviceN()
    assert cs.get_tint_transform() is None


def test_get_tint_transform_cos_returns_raw_dict() -> None:
    func = _make_type2_function([0.0], [1.0])
    cs = _build_device_n(["X"], func)
    raw = cs.get_tint_transform_cos()
    assert isinstance(raw, COSDictionary)
    assert raw.get_int("FunctionType") == 2


def test_set_tint_transform_accepts_pd_function() -> None:
    func_dict = _make_type2_function([0.0], [1.0])
    function = PDFunction.create(func_dict)
    cs = PDDeviceN()
    cs.set_tint_transform(function)
    raw = cs.get_tint_transform_cos()
    assert raw is function.get_cos_object()


def test_set_tint_transform_accepts_raw_cos() -> None:
    func_dict = _make_type2_function([0.0], [1.0])
    cs = PDDeviceN()
    cs.set_tint_transform(func_dict)
    assert cs.get_tint_transform_cos() is func_dict


def test_set_tint_transform_rejects_invalid_type() -> None:
    cs = PDDeviceN()
    with pytest.raises(TypeError):
        cs.set_tint_transform("not a function")  # type: ignore[arg-type]


# ---------- /Attributes ----------


def test_get_attributes_none_when_slot_absent() -> None:
    func = _make_type2_function([0.0], [1.0])
    cs = _build_device_n(["X"], func)
    assert cs.get_attributes() is None


def test_get_attributes_returns_wrapper_when_present() -> None:
    func = _make_type2_function([0.0], [1.0])
    attrs = COSDictionary()
    attrs.set_name("Subtype", "DeviceN")
    cs = _build_device_n(["X"], func, attributes=attrs)
    parsed = cs.get_attributes()
    assert isinstance(parsed, PDDeviceNAttributes)
    assert parsed.get_subtype() == "DeviceN"


def test_set_attributes_round_trip_then_clear() -> None:
    cs = PDDeviceN()
    attrs = PDDeviceNAttributes()
    attrs.set_subtype("NChannel")
    cs.set_attributes(attrs)
    assert cs.get_attributes() is not None
    assert cs.is_n_channel() is True

    cs.set_attributes(None)
    assert cs.get_attributes() is None
    assert cs.is_n_channel() is False


def test_is_n_channel_when_subtype_is_nchannel() -> None:
    func = _make_type2_function([0.0], [1.0])
    attrs = COSDictionary()
    attrs.set_name("Subtype", "NChannel")
    cs = _build_device_n(["X"], func, attributes=attrs)
    assert cs.is_n_channel() is True


def test_is_n_channel_false_when_subtype_is_devicen() -> None:
    func = _make_type2_function([0.0], [1.0])
    attrs = COSDictionary()
    attrs.set_name("Subtype", "DeviceN")
    cs = _build_device_n(["X"], func, attributes=attrs)
    assert cs.is_n_channel() is False


# ---------- PDDeviceNAttributes ----------


def test_attributes_subtype_round_trip() -> None:
    attrs = PDDeviceNAttributes()
    attrs.set_subtype("NChannel")
    assert attrs.is_n_channel() is True
    attrs.set_subtype("DeviceN")
    assert attrs.is_n_channel() is False
    attrs.set_subtype(None)
    assert attrs.get_subtype() is None
    assert attrs.is_n_channel() is False


def test_attributes_get_process_none_when_absent() -> None:
    assert PDDeviceNAttributes().get_process() is None


def test_attributes_get_process_returns_wrapper() -> None:
    attrs_dict = COSDictionary()
    process_dict = COSDictionary()
    process_dict.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    process_dict.set_item(
        "Components", COSArray.of_cos_names(["Cyan", "Magenta", "Yellow", "Black"])
    )
    attrs_dict.set_item("Process", process_dict)
    attrs = PDDeviceNAttributes(attrs_dict)
    process = attrs.get_process()
    assert isinstance(process, PDDeviceNProcess)
    assert process.get_components() == ["Cyan", "Magenta", "Yellow", "Black"]
    cs = process.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceCMYK"


def test_attributes_get_colorants_empty_when_absent() -> None:
    assert PDDeviceNAttributes().get_colorants() == {}


def test_attributes_get_colorants_returns_color_spaces() -> None:
    """``/Colorants`` maps colorant name → its (typically Separation)
    color space. Build a minimal map with one Separation entry and
    verify we round-trip through :meth:`PDColorSpace.create`."""
    sep_arr = COSArray()
    sep_arr.add(COSName.get_pdf_name("Separation"))
    sep_arr.add(COSName.get_pdf_name("PANTONE 185 C"))
    sep_arr.add(COSName.get_pdf_name("DeviceCMYK"))
    sep_arr.add(_make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]))

    colorants_dict = COSDictionary()
    colorants_dict.set_item("PANTONE 185 C", sep_arr)
    attrs_dict = COSDictionary()
    attrs_dict.set_item("Colorants", colorants_dict)

    attrs = PDDeviceNAttributes(attrs_dict)
    out = attrs.get_colorants()
    assert "PANTONE 185 C" in out
    sep_cs = out["PANTONE 185 C"]
    assert isinstance(sep_cs, PDSeparation)
    assert sep_cs.get_colorant_name() == "PANTONE 185 C"


def test_attributes_get_mixing_hints_round_trip() -> None:
    attrs_dict = COSDictionary()
    hints = COSDictionary()
    hints.set_int("Solidities", 1)  # arbitrary content
    attrs_dict.set_item("MixingHints", hints)
    attrs = PDDeviceNAttributes(attrs_dict)
    assert attrs.get_mixing_hints() is hints


def test_attributes_get_mixing_hints_none_when_absent() -> None:
    assert PDDeviceNAttributes().get_mixing_hints() is None


# ---------- PDDeviceNProcess ----------


def test_process_components_default_empty() -> None:
    assert PDDeviceNProcess().get_components() == []


def test_process_color_space_none_when_absent() -> None:
    assert PDDeviceNProcess().get_color_space() is None


def test_process_get_cos_dictionary_round_trip() -> None:
    d = COSDictionary()
    p = PDDeviceNProcess(d)
    assert p.get_cos_dictionary() is d


# ---------- to_rgb integration: DeviceN multi-component -> CMYK -> RGB ----------


def test_device_n_to_rgb_multi_component_via_cmyk_alternate() -> None:
    """Multi-component DeviceN with /DeviceCMYK alternate. The Type 2
    tint transform is single-input; only ``components[0]`` drives the
    output. We pick (C0=[0,0,0,0], C1=[0,1,1,0]) so input[0]=1 yields
    pure red CMYK (0,1,1,0) which converts to RGB (1,0,0)."""
    func = _make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0])
    cs = _build_device_n(["Red", "Green"], func, alternate_name="DeviceCMYK")
    rgb = PDColor([1.0, 0.5], cs).to_rgb()
    assert rgb == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)


def test_device_n_to_rgb_returns_none_without_tint_transform() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["Cyan", "Magenta"])
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    # Tint slot is still the default placeholder name
    assert cs.to_rgb([1.0, 0.5]) is None


def test_device_n_to_rgb_returns_none_without_alternate() -> None:
    """Without a real alternate color space, to_rgb falls through.
    The default placeholder name is treated as a name dispatch by
    PDColorSpace.create; the empty placeholder name returns None."""
    cs = PDDeviceN()
    cs.set_colorant_names(["A"])
    # No alternate set; the default placeholder is COSName("") which
    # PDColorSpace.create treats as unknown.
    result = cs.to_rgb([1.0])
    assert result is None


# ---------- PDDeviceCMYK is reachable for the CMYK path ----------


def test_device_n_to_rgb_uses_cmyk_path_explicitly() -> None:
    """Explicitly set the CMYK alternate via setter and verify path."""
    func = _make_type2_function([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])
    cs = PDDeviceN()
    cs.set_colorant_names(["Black"])
    cs.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    cs.set_tint_transform(func)
    rgb = cs.to_rgb([1.0])
    assert rgb == (0.0, 0.0, 0.0)

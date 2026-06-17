"""Hand-written tests for :class:`PDDeviceN` covering the seven
required accessors per the project's task scope:
``get_colorant_names`` / ``get_alternate_color_space`` /
``get_tint_transform`` / ``get_attributes`` / ``get_subtype`` /
``get_process_color_space`` / ``to_rgb(tints)``.

Companion to ``test_pd_device_n_parity.py`` which is the deeper round-out
suite. This file is the focused contract test for the task's named API
surface — keeping a small, hand-readable spec grounded in PDF 32000-1
§8.6.6.5 close to the round-out work.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
    PDDeviceNProcess,
)
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB

# ---------- helpers ----------


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    """Build a /FunctionType 2 (exponential) dict for tint transforms."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _device_n(
    colorants: list[str],
    tint: COSDictionary,
    alternate: str = "DeviceCMYK",
    attributes: COSDictionary | None = None,
) -> PDDeviceN:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray.of_cos_names(colorants))
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(tint)
    if attributes is not None:
        arr.add(attributes)
    return PDDeviceN(arr)


# ---------- get_name ----------


def test_get_name_returns_device_n() -> None:
    assert PDDeviceN().get_name() == "DeviceN"


def test_name_constant_matches() -> None:
    assert PDDeviceN.NAME == "DeviceN"


# ---------- get_colorant_names ----------


def test_get_colorant_names_round_trip_via_array() -> None:
    cs = _device_n(
        ["Cyan", "Magenta", "Yellow", "Black"],
        _type2([0.0] * 4, [1.0] * 4),
    )
    assert cs.get_colorant_names() == ["Cyan", "Magenta", "Yellow", "Black"]


def test_get_colorant_names_round_trip_via_setter() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A", "B", "C"])
    assert cs.get_colorant_names() == ["A", "B", "C"]


def test_get_number_of_components_matches_colorant_count() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A", "B", "C", "D", "E"])
    assert cs.get_number_of_components() == 5


def test_get_default_decode_is_zero_one_per_colorant() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A", "B"])
    assert cs.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0]


# ---------- get_alternate_color_space ----------


def test_get_alternate_color_space_resolves_named() -> None:
    cs = _device_n(["X"], _type2([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]), alternate="DeviceRGB")
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceRGB"


def test_alternate_round_trip_via_setter() -> None:
    cs = PDDeviceN()
    cs.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceCMYK"


# ---------- get_tint_transform ----------


def test_get_tint_transform_returns_pd_function() -> None:
    cs = _device_n(["X"], _type2([0.0], [1.0]))
    fn = cs.get_tint_transform()
    assert isinstance(fn, PDFunction)
    assert fn.get_function_type() == 2


def test_get_tint_transform_none_for_default_placeholder() -> None:
    assert PDDeviceN().get_tint_transform() is None


# ---------- get_attributes ----------


def test_get_attributes_none_when_slot_absent() -> None:
    cs = _device_n(["X"], _type2([0.0], [1.0]))
    assert cs.get_attributes() is None


def test_get_attributes_returns_wrapper_when_present() -> None:
    attrs_dict = COSDictionary()
    attrs_dict.set_name("Subtype", "DeviceN")
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=attrs_dict)
    parsed = cs.get_attributes()
    assert isinstance(parsed, PDDeviceNAttributes)
    assert parsed.get_subtype() == "DeviceN"


def test_set_attributes_round_trip_then_clear() -> None:
    cs = PDDeviceN()
    attrs = PDDeviceNAttributes()
    attrs.set_subtype("NChannel")
    cs.set_attributes(attrs)
    assert cs.get_attributes() is not None
    cs.set_attributes(None)
    assert cs.get_attributes() is None


# ---------- get_subtype (NChannel / DeviceN) ----------


def test_get_subtype_devicen_when_no_attributes() -> None:
    """No /Attributes -> implicit subtype is plain DeviceN (PDF 1.6
    NChannel must opt-in via /Subtype)."""
    cs = _device_n(["X"], _type2([0.0], [1.0]))
    assert cs.get_subtype() == "DeviceN"


def test_get_subtype_devicen_when_subtype_absent_in_attributes() -> None:
    """Empty /Attributes (no /Subtype) -> implicit subtype DeviceN."""
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=COSDictionary())
    assert cs.get_subtype() == "DeviceN"


def test_get_subtype_devicen_explicit() -> None:
    attrs = COSDictionary()
    attrs.set_name("Subtype", "DeviceN")
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=attrs)
    assert cs.get_subtype() == "DeviceN"


def test_get_subtype_nchannel_explicit() -> None:
    attrs = COSDictionary()
    attrs.set_name("Subtype", "NChannel")
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=attrs)
    assert cs.get_subtype() == "NChannel"


def test_get_subtype_unknown_value_falls_back_to_devicen() -> None:
    """An unrecognised /Subtype value is treated as plain DeviceN
    rather than propagated — keeps the consumer surface 2-valued."""
    attrs = COSDictionary()
    attrs.set_name("Subtype", "Bogus")
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=attrs)
    assert cs.get_subtype() == "DeviceN"


def test_is_n_channel_aligned_with_get_subtype() -> None:
    cs = PDDeviceN()
    attrs = PDDeviceNAttributes()
    attrs.set_subtype("NChannel")
    cs.set_attributes(attrs)
    assert cs.is_n_channel() is True
    assert cs.get_subtype() == "NChannel"


# ---------- get_process_color_space ----------


def test_get_process_color_space_none_when_no_attributes() -> None:
    cs = _device_n(["X"], _type2([0.0], [1.0]))
    assert cs.get_process_color_space() is None


def test_get_process_color_space_none_when_no_process() -> None:
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=COSDictionary())
    assert cs.get_process_color_space() is None


def test_get_process_color_space_returns_named_cmyk() -> None:
    """/Attributes/Process/ColorSpace = /DeviceCMYK is resolved through
    PDColorSpace.create."""
    process = COSDictionary()
    process.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    process.set_item(
        "Components",
        COSArray.of_cos_names(["Cyan", "Magenta", "Yellow", "Black"]),
    )
    attrs = COSDictionary()
    attrs.set_item("Process", process)
    cs = _device_n(["Cyan", "Magenta", "Yellow", "Black"], _type2([0.0], [1.0]), attributes=attrs)
    proc_cs = cs.get_process_color_space()
    assert proc_cs is not None
    assert proc_cs.get_name() == "DeviceCMYK"


def test_get_process_color_space_returns_rgb() -> None:
    process = COSDictionary()
    process.set_item("ColorSpace", COSName.get_pdf_name("DeviceRGB"))
    process.set_item("Components", COSArray.of_cos_names(["Red", "Green", "Blue"]))
    attrs = COSDictionary()
    attrs.set_item("Process", process)
    cs = _device_n(["Red", "Green", "Blue"], _type2([0.0], [1.0]), attributes=attrs)
    proc_cs = cs.get_process_color_space()
    assert proc_cs is not None
    assert proc_cs.get_name() == "DeviceRGB"


# ---------- to_rgb(tints) ----------


def test_to_rgb_via_cmyk_red() -> None:
    """Multi-component DeviceN over CMYK alternate. Tint transform is
    single-input (the standard PDFBox single-tint model); input[0]=1
    yields CMYK (0,1,1,0) -> RGB (1,0,0)."""
    cs = _device_n(
        ["Red", "Green"],
        _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]),
        alternate="DeviceCMYK",
    )
    rgb = cs.to_rgb([1.0, 0.5])
    assert rgb == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)


def test_to_rgb_returns_none_without_tint_transform() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A"])
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    assert cs.to_rgb([1.0]) is None


def test_to_rgb_returns_none_without_alternate() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A"])
    cs.set_tint_transform(_type2([0.0], [1.0]))
    assert cs.to_rgb([1.0]) is None


def test_to_rgb_round_trip_via_pd_color() -> None:
    """PDColor.to_rgb on a DeviceN must agree with cs.to_rgb."""
    cs = _device_n(
        ["Black"],
        _type2([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]),
        alternate="DeviceCMYK",
    )
    via_color = PDColor([1.0], cs).to_rgb()
    via_cs = cs.to_rgb([1.0])
    assert via_color == via_cs == (0.0, 0.0, 0.0)


# ---------- PDDeviceNAttributes / PDDeviceNProcess sanity ----------


def test_attributes_subtype_round_trip_through_setter() -> None:
    a = PDDeviceNAttributes()
    a.set_subtype("NChannel")
    assert a.is_n_channel() is True
    a.set_subtype(None)
    assert a.get_subtype() is None
    assert a.is_n_channel() is False


def test_process_components_default_empty() -> None:
    assert PDDeviceNProcess().get_components() == []


def test_process_color_space_returns_typed_cs() -> None:
    d = COSDictionary()
    d.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    d.set_item(
        "Components",
        COSArray.of_cos_names(["Cyan", "Magenta", "Yellow", "Black"]),
    )
    p = PDDeviceNProcess(d)
    assert p.get_components() == ["Cyan", "Magenta", "Yellow", "Black"]
    cs = p.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceCMYK"


# ---------- initial color ----------


def test_initial_color_is_full_tint_per_colorant() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A", "B", "C"])
    initial = cs.get_initial_color()
    assert initial.get_components() == [1.0, 1.0, 1.0]

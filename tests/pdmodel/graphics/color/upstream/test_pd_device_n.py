"""Upstream-aligned tests for :class:`PDDeviceN`.

Apache PDFBox does not ship a dedicated ``PDDeviceNTest.java`` — the
DeviceN code path is exercised indirectly through PDFRenderer regression
fixtures that depend on AWT raster rendering. Those fixture-driven tests
do not translate cleanly to a Python port. Instead this file covers the
behavioural surface that the upstream ``PDDeviceN.java`` source itself
defines as contract:

- constructor seeds ``[/DeviceN, null, null, null]``
- ``set_colorant_names`` writes index ``COLORANT_NAMES``
- ``set_alternate_color_space`` writes index ``ALTERNATE_CS``
- ``set_tint_transform`` writes index ``TINT_TRANSFORM``
- ``set_attributes(None)`` removes index ``DEVICEN_ATTRIBUTES``
- ``set_attributes(...)`` grows the array if needed
- ``get_default_decode`` returns ``[0, 1]`` per component
- ``get_initial_color`` is full tint per colorant
- ``is_n_channel`` reflects ``/Subtype = NChannel``
- ``to_rgb`` dispatches between attribute / tint-transform paths
- ``to_raw_image`` returns ``None`` (DeviceN has no raw form)
- ``to_string`` mirrors ``__str__``
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
    PDDeviceNProcess,
)
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
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


# ---------- constructor ----------


def test_default_constructor_seeds_four_array_slots() -> None:
    cs = PDDeviceN()
    assert cs.get_cos_object().size() == 4


def test_default_constructor_first_slot_is_devicen_name() -> None:
    cs = PDDeviceN()
    head = cs.get_cos_object().get(0)
    assert isinstance(head, COSName)
    assert head.get_name() == "DeviceN"


def test_default_constructor_no_attributes_slot() -> None:
    assert PDDeviceN().get_attributes() is None


def test_default_constructor_zero_components() -> None:
    assert PDDeviceN().get_number_of_components() == 0


# ---------- get_default_decode ----------


def test_get_default_decode_3_components() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A", "B", "C"])
    assert cs.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_get_default_decode_zero_components() -> None:
    assert PDDeviceN().get_default_decode(8) == []


# ---------- get_initial_color ----------


def test_initial_color_is_one_per_component() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A", "B", "C", "D"])
    assert cs.get_initial_color().get_components() == [1.0, 1.0, 1.0, 1.0]


def test_initial_color_refreshes_after_set_colorant_names() -> None:
    """Upstream computes the initial color in the constructor; we recompute
    on the accessor so the contract holds after late ``set_colorant_names``."""
    cs = PDDeviceN()
    cs.set_colorant_names(["A"])
    assert cs.get_initial_color().get_components() == [1.0]
    cs.set_colorant_names(["A", "B", "C"])
    assert cs.get_initial_color().get_components() == [1.0, 1.0, 1.0]


# ---------- set_alternate_color_space / get_alternate_color_space ----------


def test_set_alternate_color_space_round_trip_devicergb() -> None:
    cs = PDDeviceN()
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceRGB"


def test_set_alternate_color_space_round_trip_devicecmyk() -> None:
    cs = PDDeviceN()
    cs.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    alt = cs.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceCMYK"


# ---------- set_attributes / get_attributes ----------


def test_set_attributes_grows_array() -> None:
    """Upstream's setAttributes mutates index 4 of the array, growing it
    with COSNull.NULL placeholders if needed."""
    cs = PDDeviceN()
    assert cs.get_cos_object().size() == 4
    attrs = PDDeviceNAttributes()
    attrs.set_subtype("NChannel")
    cs.set_attributes(attrs)
    assert cs.get_cos_object().size() == 5
    assert cs.get_attributes() is not None


def test_set_attributes_none_removes_slot() -> None:
    cs = _device_n(
        ["X"], _type2([0.0], [1.0]), attributes=COSDictionary()
    )
    assert cs.get_cos_object().size() == 5
    cs.set_attributes(None)
    assert cs.get_cos_object().size() == 4
    assert cs.get_attributes() is None


def test_clear_attributes_alias() -> None:
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=COSDictionary())
    cs.clear_attributes()
    assert cs.get_attributes() is None


# ---------- is_n_channel ----------


def test_is_n_channel_false_when_no_attributes() -> None:
    assert PDDeviceN().is_n_channel() is False


def test_is_n_channel_false_when_subtype_devicen() -> None:
    attrs = COSDictionary()
    attrs.set_name("Subtype", "DeviceN")
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=attrs)
    assert cs.is_n_channel() is False


def test_is_n_channel_true_when_subtype_nchannel() -> None:
    attrs = COSDictionary()
    attrs.set_name("Subtype", "NChannel")
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=attrs)
    assert cs.is_n_channel() is True


# ---------- to_rgb dispatch ----------


def test_to_rgb_no_attributes_uses_tint_transform_path() -> None:
    """Without /Attributes, to_rgb evaluates the tint transform and
    forwards to the alternate color space."""
    cs = _device_n(
        ["Red"],
        _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]),
        alternate="DeviceCMYK",
    )
    assert cs.to_rgb([1.0]) is not None


def test_to_rgb_with_tint_transform_returns_none_without_alternate() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A"])
    cs.set_tint_transform(_type2([0.0], [1.0]))
    assert cs.to_rgb_with_tint_transform([1.0]) is None


def test_to_rgb_with_tint_transform_returns_none_without_function() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A"])
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    assert cs.to_rgb_with_tint_transform([1.0]) is None


def test_to_rgb_with_attributes_falls_back_to_tint_when_spot_missing() -> None:
    """When a colorant has no entry in /Colorants and is not a process
    component, upstream falls back to the tint-transform path."""
    attrs = COSDictionary()
    attrs.set_name("Subtype", "DeviceN")
    cs = _device_n(
        ["UnmappedSpot"],
        _type2(
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0, 0.0],
        ),
        alternate="DeviceCMYK",
        attributes=attrs,
    )
    rgb = cs.to_rgb_with_attributes([1.0])
    assert rgb is not None
    # Tint transform sends [1] to CMYK [0,1,1,0] which is RGB red.
    assert rgb[0] > rgb[1]
    assert rgb[0] > rgb[2]


# ---------- init_color_conversion_cache ----------


def test_init_color_conversion_cache_no_op_without_attributes() -> None:
    cs = PDDeviceN()
    cs.set_colorant_names(["A"])
    cs.init_color_conversion_cache()
    assert cs._num_colorants == 0
    assert cs._spot_color_spaces == []


def test_init_color_conversion_cache_indexes_process_components() -> None:
    """When /Process declares Cyan/Magenta/Yellow/Black components and
    the colorants list aligns, each colorant should map to its
    corresponding process index."""
    process = COSDictionary()
    process.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    process.set_item(
        "Components",
        COSArray.of_cos_names(["Cyan", "Magenta", "Yellow", "Black"]),
    )
    attrs = COSDictionary()
    attrs.set_item("Process", process)
    cs = _device_n(
        ["Cyan", "Magenta", "Yellow", "Black"],
        _type2([0.0], [1.0]),
        attributes=attrs,
    )
    cs.init_color_conversion_cache()
    assert cs._num_colorants == 4
    assert cs._colorant_to_component == [0, 1, 2, 3]
    assert cs._process_color_space is not None
    assert cs._process_color_space.get_name() == "DeviceCMYK"


def test_init_color_conversion_cache_marks_unknown_as_minus_one() -> None:
    process = COSDictionary()
    process.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    process.set_item(
        "Components",
        COSArray.of_cos_names(["Cyan", "Magenta", "Yellow", "Black"]),
    )
    attrs = COSDictionary()
    attrs.set_item("Process", process)
    cs = _device_n(
        ["SpotOnly"], _type2([0.0], [1.0]), attributes=attrs
    )
    cs.init_color_conversion_cache()
    assert cs._colorant_to_component == [-1]


# ---------- to_raw_image ----------


def test_to_raw_image_returns_none() -> None:
    """Mirrors upstream contract — DeviceN has no raw raster form."""
    cs = PDDeviceN()
    cs.set_colorant_names(["A", "B"])
    assert cs.to_raw_image(b"\x00\x00", 1, 1) is None


# ---------- to_string ----------


def test_to_string_matches_dunder_str() -> None:
    cs = _device_n(
        ["Cyan", "Magenta"],
        _type2([0.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]),
        alternate="DeviceCMYK",
    )
    assert cs.to_string() == str(cs)


def test_to_string_starts_with_devicen() -> None:
    cs = _device_n(["A"], _type2([0.0], [1.0]))
    assert cs.to_string().startswith("DeviceN{")


# ---------- attributes / process wrapper sanity ----------


def test_process_wrapper_round_trip() -> None:
    p = PDDeviceNProcess()
    p.set_components(["Red", "Green", "Blue"])
    p.set_color_space(PDDeviceRGB.INSTANCE)
    assert p.get_components() == ["Red", "Green", "Blue"]
    cs = p.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"


def test_attributes_subtype_default_devicen() -> None:
    attrs = PDDeviceNAttributes()
    assert attrs.is_n_channel() is False

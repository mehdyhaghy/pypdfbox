"""Wave 1368 round-out tests for ``pypdfbox.pdmodel.graphics.color.pd_device_n``.

Targets the per-color-space tinting / lookup / conversion functions on
:class:`PDDeviceN`:

- ``/Names`` colorant array round-trip + ``get_colorant_index`` lookup
- ``/AlternateSpace`` get/set/has/clear surface
- ``/TintTransform`` dispatch (PDFunction-type-2 exponential)
- ``/Attributes`` dictionary with /Process colorants vs /Colorants spot
  colorants, and the NChannel vs DeviceN subtype divergence
- ``to_rgb`` tint-transform path versus attribute-driven path
- ``init_color_conversion_cache`` shape (process / spot / collision)
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
)
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
    PDDeviceNProcess,
)
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- helpers ----------


def _make_type2_identity(n_in: int = 1, n_out: int = 1) -> COSDictionary:
    """Build a /FunctionType 2 exponential function dict that maps the
    input(s) verbatim to the output(s) — ``y = x ** 1.0`` per component.
    """
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain = COSArray()
    for _ in range(n_in):
        domain.add(COSFloat(0.0))
        domain.add(COSFloat(1.0))
    d.set_item(COSName.get_pdf_name("Domain"), domain)
    rng = COSArray()
    for _ in range(n_out):
        rng.add(COSFloat(0.0))
        rng.add(COSFloat(1.0))
    d.set_item(COSName.get_pdf_name("Range"), rng)
    c0 = COSArray()
    c1 = COSArray()
    for _ in range(n_out):
        c0.add(COSFloat(0.0))
        c1.add(COSFloat(1.0))
    d.set_item(COSName.get_pdf_name("C0"), c0)
    d.set_item(COSName.get_pdf_name("C1"), c1)
    d.set_item(COSName.get_pdf_name("N"), COSFloat(1.0))
    return d


def _make_devicen(
    names: list[str],
    alternate: PDColorSpace,
    tint: COSDictionary | None = None,
    attributes: COSDictionary | None = None,
) -> PDDeviceN:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    names_array = COSArray()
    for n in names:
        names_array.add(COSName.get_pdf_name(n))
    arr.add(names_array)
    arr.add(alternate.get_cos_object())
    arr.add(tint if tint is not None else _make_type2_identity(len(names), 3))
    if attributes is not None:
        arr.add(attributes)
    return PDDeviceN(arr)


# ---------- colorant names + index ----------


def test_colorant_names_round_trip() -> None:
    cs = _make_devicen(["Cyan", "Magenta", "Yellow"], PDDeviceRGB.INSTANCE)
    assert cs.get_colorant_names() == ["Cyan", "Magenta", "Yellow"]
    assert cs.get_number_of_components() == 3


def test_set_colorant_names_replaces_existing() -> None:
    cs = _make_devicen(["Cyan"], PDDeviceRGB.INSTANCE)
    cs.set_colorant_names(["Red", "Green", "Blue"])
    assert cs.get_colorant_names() == ["Red", "Green", "Blue"]
    assert cs.get_number_of_components() == 3


def test_get_colorant_index_returns_minus_one_when_missing() -> None:
    cs = _make_devicen(["Cyan", "Yellow"], PDDeviceRGB.INSTANCE)
    assert cs.get_colorant_index("Cyan") == 0
    assert cs.get_colorant_index("Yellow") == 1
    assert cs.get_colorant_index("Magenta") == -1


# ---------- alternate color space ----------


def test_alternate_color_space_round_trip() -> None:
    cs = _make_devicen(["Spot1"], PDDeviceRGB.INSTANCE)
    alt = cs.get_alternate_color_space()
    assert alt is PDDeviceRGB.INSTANCE
    assert cs.has_alternate_color_space() is True

    cs.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    assert cs.get_alternate_color_space() is PDDeviceCMYK.INSTANCE


# ---------- tint transform ----------


def test_tint_transform_dispatch_returns_pdfunction() -> None:
    cs = _make_devicen(["Spot1"], PDDeviceRGB.INSTANCE)
    fn = cs.get_tint_transform()
    assert fn is not None
    assert fn.get_function_type() == 2
    assert cs.has_tint_transform() is True


def test_tint_transform_placeholder_returns_none() -> None:
    """Default ctor leaves the tint-transform slot as a COSName placeholder."""
    cs = PDDeviceN()
    assert cs.get_tint_transform() is None
    assert cs.has_tint_transform() is False


def test_clear_tint_transform_resets_to_placeholder() -> None:
    cs = _make_devicen(["Spot1"], PDDeviceRGB.INSTANCE)
    assert cs.has_tint_transform()
    cs.clear_tint_transform()
    assert cs.has_tint_transform() is False


def test_set_tint_transform_with_pdfunction_wrapper() -> None:
    cs = _make_devicen(["Spot1"], PDDeviceRGB.INSTANCE)
    new_fn = PDFunction.create(_make_type2_identity(1, 3))
    cs.set_tint_transform(new_fn)
    fn = cs.get_tint_transform()
    assert fn is not None
    assert fn.get_function_type() == 2


# ---------- /Attributes dictionary ----------


def test_attributes_absent_returns_none() -> None:
    cs = _make_devicen(["Spot1"], PDDeviceRGB.INSTANCE)
    assert cs.get_attributes() is None
    assert cs.has_attributes() is False
    # When /Attributes is absent the subtype implicitly defaults to "DeviceN".
    assert cs.get_subtype() == "DeviceN"
    assert cs.is_n_channel() is False


def test_attributes_with_nchannel_subtype() -> None:
    attrs_dict = COSDictionary()
    attrs_dict.set_name(COSName.get_pdf_name("Subtype"), "NChannel")
    cs = _make_devicen(
        ["Cyan", "Magenta"], PDDeviceRGB.INSTANCE, attributes=attrs_dict
    )
    assert cs.has_attributes() is True
    assert cs.is_n_channel() is True
    assert cs.get_subtype() == "NChannel"


def test_attributes_devicen_subtype_falls_back_when_unknown() -> None:
    attrs_dict = COSDictionary()
    attrs_dict.set_name(COSName.get_pdf_name("Subtype"), "Bogus")
    cs = _make_devicen(["Spot"], PDDeviceRGB.INSTANCE, attributes=attrs_dict)
    # Unknown subtype names should fall back to "DeviceN" (NChannel must
    # opt in explicitly per PDF 32000-1 §8.6.6.5).
    assert cs.get_subtype() == "DeviceN"


def test_set_attributes_round_trips_dictionary() -> None:
    cs = _make_devicen(["Spot1"], PDDeviceRGB.INSTANCE)
    attrs_dict = COSDictionary()
    attrs_dict.set_name(COSName.get_pdf_name("Subtype"), "NChannel")
    cs.set_attributes(PDDeviceNAttributes(attrs_dict))
    assert cs.is_n_channel()
    # Clear puts us back to no /Attributes.
    cs.clear_attributes()
    assert cs.get_attributes() is None


# ---------- /Process colorants ----------


def test_process_color_space_round_trip() -> None:
    process_dict = COSDictionary()
    process_dict.set_item(
        COSName.get_pdf_name("ColorSpace"),
        PDDeviceCMYK.INSTANCE.get_cos_object(),
    )
    components = COSArray()
    for name in ["Cyan", "Magenta", "Yellow", "Black"]:
        components.add(COSName.get_pdf_name(name))
    process_dict.set_item(COSName.get_pdf_name("Components"), components)

    attrs_dict = COSDictionary()
    attrs_dict.set_item(COSName.get_pdf_name("Process"), process_dict)

    cs = _make_devicen(
        ["Cyan", "Magenta", "Yellow", "Black"],
        PDDeviceRGB.INSTANCE,
        attributes=attrs_dict,
    )
    process = cs.get_attributes().get_process()
    assert process is not None
    assert process.has_color_space() is True
    assert process.has_components() is True
    assert process.get_components() == ["Cyan", "Magenta", "Yellow", "Black"]
    process_cs = cs.get_process_color_space()
    assert process_cs is PDDeviceCMYK.INSTANCE


def test_process_clear_components_and_color_space() -> None:
    process = PDDeviceNProcess()
    process.set_color_space(PDDeviceRGB.INSTANCE)
    process.set_components(["R", "G", "B"])
    assert process.has_color_space() and process.has_components()
    process.clear_components()
    process.clear_color_space()
    assert process.has_components() is False
    assert process.has_color_space() is False


# ---------- /Colorants spot colorants ----------


def test_colorants_get_set_round_trip() -> None:
    attrs = PDDeviceNAttributes()
    attrs.set_colorants({"Spot1": PDDeviceRGB.INSTANCE})
    colorants = attrs.get_colorants()
    assert set(colorants.keys()) == {"Spot1"}
    assert colorants["Spot1"] is PDDeviceRGB.INSTANCE
    assert attrs.has_colorants() is True
    attrs.clear_colorants()
    assert attrs.has_colorants() is False


# ---------- color conversion: tint-transform path ----------


def test_to_rgb_uses_tint_transform_when_no_attributes() -> None:
    """Identity tint transform routes (0.5, 0.5, 0.5) through DeviceRGB."""
    cs = _make_devicen(["A", "B", "C"], PDDeviceRGB.INSTANCE)
    rgb = cs.to_rgb([0.5, 0.5, 0.5])
    assert rgb is not None
    r, g, b = rgb
    assert 0.0 <= r <= 1.0
    assert 0.0 <= g <= 1.0
    assert 0.0 <= b <= 1.0


def test_to_rgb_returns_none_when_alternate_missing() -> None:
    """A DeviceN whose alternate slot is unresolvable can't convert."""
    cs = PDDeviceN()
    # Default ctor leaves alternate slot as a COSName placeholder; the
    # tint-transform path has no valid alternate to recurse into.
    assert cs.get_alternate_color_space() is None
    assert cs.to_rgb([0.5]) is None


# ---------- color conversion: attribute-driven path ----------


def test_init_color_conversion_cache_resets_state_when_no_attributes() -> None:
    cs = _make_devicen(["Cyan"], PDDeviceRGB.INSTANCE)
    # Pre-populate the cache as if a previous wave-1368 read had ran
    cs._num_colorants = 99
    cs._colorant_to_component = [42]
    cs._spot_color_spaces = [PDDeviceRGB.INSTANCE]
    cs._process_color_space = PDDeviceRGB.INSTANCE
    cs.init_color_conversion_cache()
    assert cs._num_colorants == 0
    assert cs._colorant_to_component == []
    assert cs._spot_color_spaces == []
    assert cs._process_color_space is None


def test_init_color_conversion_cache_maps_process_components() -> None:
    process_dict = COSDictionary()
    process_dict.set_item(
        COSName.get_pdf_name("ColorSpace"),
        PDDeviceCMYK.INSTANCE.get_cos_object(),
    )
    components = COSArray()
    for name in ["Cyan", "Magenta", "Yellow", "Black"]:
        components.add(COSName.get_pdf_name(name))
    process_dict.set_item(COSName.get_pdf_name("Components"), components)
    attrs_dict = COSDictionary()
    attrs_dict.set_item(COSName.get_pdf_name("Process"), process_dict)
    cs = _make_devicen(
        ["Cyan", "Magenta", "Yellow", "Black"],
        PDDeviceRGB.INSTANCE,
        attributes=attrs_dict,
    )
    cs.init_color_conversion_cache()
    # All four colorants map onto process components in their declared order.
    assert cs._num_colorants == 4
    assert cs._colorant_to_component == [0, 1, 2, 3]
    assert cs._process_color_space is PDDeviceCMYK.INSTANCE


def test_init_color_conversion_cache_spot_colorant_masks_process_in_devicen() -> None:
    """A spot colorant of the same name masks the process slot for DeviceN."""
    # /Process declares "Magenta" as a process colorant
    process_dict = COSDictionary()
    process_dict.set_item(
        COSName.get_pdf_name("ColorSpace"),
        PDDeviceRGB.INSTANCE.get_cos_object(),
    )
    components = COSArray()
    components.add(COSName.get_pdf_name("Magenta"))
    process_dict.set_item(COSName.get_pdf_name("Components"), components)
    # /Colorants also declares "Magenta" → in DeviceN this masks the
    # process component (PDF 32000-1 §8.6.6.5).
    spot_sep = PDSeparation()
    spot_sep.set_colorant_name("Magenta")
    spot_sep.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    spot_sep.set_tint_transform(_make_type2_identity(1, 4))
    spot_cos = COSDictionary()
    spot_cos.set_item("Magenta", spot_sep.get_cos_object())

    attrs_dict = COSDictionary()
    attrs_dict.set_item(COSName.get_pdf_name("Process"), process_dict)
    attrs_dict.set_item(COSName.get_pdf_name("Colorants"), spot_cos)
    # No /Subtype → defaults to "DeviceN" (not "NChannel").
    cs = _make_devicen(["Magenta"], PDDeviceRGB.INSTANCE, attributes=attrs_dict)
    cs.init_color_conversion_cache()
    # Spot overrides the process mapping back to -1.
    assert cs._colorant_to_component == [-1]
    assert cs._spot_color_spaces[0] is not None


def test_init_color_conversion_cache_spot_preserves_process_for_nchannel() -> None:
    """For NChannel subtype the spot colorant does NOT mask the process slot."""
    process_dict = COSDictionary()
    process_dict.set_item(
        COSName.get_pdf_name("ColorSpace"),
        PDDeviceRGB.INSTANCE.get_cos_object(),
    )
    components = COSArray()
    components.add(COSName.get_pdf_name("Magenta"))
    process_dict.set_item(COSName.get_pdf_name("Components"), components)
    spot_sep = PDSeparation()
    spot_sep.set_colorant_name("Magenta")
    spot_sep.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    spot_sep.set_tint_transform(_make_type2_identity(1, 4))
    spot_cos = COSDictionary()
    spot_cos.set_item("Magenta", spot_sep.get_cos_object())

    attrs_dict = COSDictionary()
    attrs_dict.set_name(COSName.get_pdf_name("Subtype"), "NChannel")
    attrs_dict.set_item(COSName.get_pdf_name("Process"), process_dict)
    attrs_dict.set_item(COSName.get_pdf_name("Colorants"), spot_cos)
    cs = _make_devicen(["Magenta"], PDDeviceRGB.INSTANCE, attributes=attrs_dict)
    cs.init_color_conversion_cache()
    # NChannel keeps the process mapping at 0 even when /Colorants names it.
    assert cs._colorant_to_component == [0]


# ---------- DeviceN string form ----------


def test_to_string_includes_all_colorants_and_alternate() -> None:
    cs = _make_devicen(["A", "B"], PDDeviceGray.INSTANCE)
    s = cs.to_string()
    assert "DeviceN{" in s
    assert '"A"' in s
    assert '"B"' in s
    assert "DeviceGray" in s


# ---------- default decode ----------


def test_default_decode_is_unit_pair_per_colorant() -> None:
    cs = _make_devicen(["A", "B", "C"], PDDeviceRGB.INSTANCE)
    assert cs.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


# ---------- initial color ----------


def test_initial_color_is_full_tint_per_component() -> None:
    cs = _make_devicen(["A", "B"], PDDeviceRGB.INSTANCE)
    initial = cs.get_initial_color()
    # PDDeviceN.get_initial_color uses full tint (1.0) per component.
    assert initial._components == [1.0, 1.0]


def test_initial_color_refreshes_after_colorant_resize() -> None:
    cs = _make_devicen(["A"], PDDeviceRGB.INSTANCE)
    cs.set_colorant_names(["A", "B", "C"])
    initial = cs.get_initial_color()
    assert initial._components == [1.0, 1.0, 1.0]


def test_make_type2_function_dictionary_is_valid_input() -> None:
    """Smoke: the helper produces a working PDFunction directly."""
    fn = PDFunction.create(_make_type2_identity(1, 3))
    assert fn is not None
    assert fn.get_function_type() == 2
    out = fn.eval([0.7])
    assert len(out) == 3

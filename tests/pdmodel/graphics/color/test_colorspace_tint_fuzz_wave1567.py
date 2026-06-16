"""Wave 1567 fuzz coverage for the tint-transform / lookup-table /
N-fallback edges of the Separation, DeviceN, ICCBased, and Indexed color
spaces. Each assertion is pinned to the documented behaviour of upstream
PDFBox 3.0.7 (``PDSeparation``/``PDDeviceN``/``PDICCBased``/``PDIndexed``):

- Separation tint transform: tint in ``[0, 1]`` -> N alternate components
  -> RGB, plus the ``(int)(tint * 255)`` quantised ``toRGBMap`` cache and
  out-of-range tints.
- DeviceN with multiple colorants over a Type-4 PostScript tint transform
  and the ``/Attributes`` process-component path.
- ICCBased ``/N`` fallback to DeviceGray/RGB/CMYK when no profile is
  embedded, plus the initial-colour shape (CMYK alternate -> ``(0,0,0,1)``).
- Indexed lookup-table bounds: ``hival`` clamping, index ``< 0`` / ``>
  hival`` clamping (``Math.round`` round-half-up), truncated lookup data,
  and ``get_initial_color`` defaults.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- helpers ----------


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    """A Type-2 (exponential interpolation) PDF function, 1 input -> len(c0)
    outputs. Mirrors the kind of tint transform Separation arrays carry."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _type4(code: bytes, n_in: int, n_out: int) -> COSStream:
    """A Type-4 (PostScript calculator) tint transform over ``n_in`` inputs
    and ``n_out`` outputs, both with the ``[0, 1]`` domain/range."""
    ps = COSStream()
    ps.set_int("FunctionType", 4)
    ps.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0] * n_in))
    ps.set_item("Range", COSArray.of_cos_floats([0.0, 1.0] * n_out))
    with ps.create_output_stream() as out:
        out.write(code)
    return ps


def _separation(
    tint: COSDictionary | COSStream,
    colorant: str = "Spot",
    alternate: str = "DeviceCMYK",
) -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(tint)
    return PDSeparation(arr)


def _devicen(
    colorants: list[str],
    tint: COSStream,
    alternate: str = "DeviceCMYK",
    attributes: COSDictionary | None = None,
) -> PDDeviceN:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    names = COSArray()
    for c in colorants:
        names.add(COSName.get_pdf_name(c))
    arr.add(names)
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(tint)
    if attributes is not None:
        arr.add(attributes)
    return PDDeviceN(arr)


def _iccbased(n: int, alternate: str | None = None) -> PDICCBased:
    """An ICCBased color space with no embedded profile body, so the
    /N-driven fallback path is exercised."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("N"), n)
    if alternate is not None:
        stream.set_item(
            COSName.get_pdf_name("Alternate"), COSName.get_pdf_name(alternate)
        )
    arr.add(stream)
    return PDICCBased(arr)


def _indexed(base, hival: int, lookup: bytes) -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(base.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(COSString(lookup))
    return PDIndexed(arr)


def _approx(a, b, tol: float = 1e-4) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b, strict=False))


# ---------- Separation: tint transform ----------


def test_separation_tint_zero_to_cmyk_white() -> None:
    # C0=(0,0,0,0) -> CMYK all zero -> white.
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    assert _approx(sep.to_rgb([0.0]), (1.0, 1.0, 1.0))


def test_separation_tint_full_to_cmyk_black() -> None:
    # C1=(0,0,0,1) -> K=1 -> black.
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    assert _approx(sep.to_rgb([1.0]), (0.0, 0.0, 0.0))


def test_separation_tint_half_linear() -> None:
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    assert _approx(sep.to_rgb([0.5]), (0.5, 0.5, 0.5))


def test_separation_tint_rgb_alternate() -> None:
    # Alternate DeviceRGB; C1 = pure red.
    sep = _separation(
        _type2([1, 1, 1], [1, 0, 0]), alternate="DeviceRGB"
    )
    assert _approx(sep.to_rgb([1.0]), (1.0, 0.0, 0.0))


def test_separation_tint_quantised_cache_hit() -> None:
    # toRGBMap is keyed on (int)(tint*255); 0.500 and 0.5009 both map to
    # key 127 so the second call returns the cached first result verbatim.
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    first = sep.to_rgb([0.5])
    again = sep.to_rgb([0.5 + 0.5 / 255.0 - 1e-6])
    assert again == first
    assert int(0.5 * 255) == int((0.5 + 0.5 / 255.0 - 1e-6) * 255)


def test_separation_initial_color_single_full_tint() -> None:
    # Upstream: new PDColor(new float[]{1}, this).
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    assert sep.get_initial_color().get_components() == [1.0]


def test_separation_number_of_components_is_one() -> None:
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    assert sep.get_number_of_components() == 1


def test_separation_default_decode_full_range() -> None:
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    assert sep.get_default_decode(8) == [0.0, 1.0]


def test_separation_default_ctor_no_alternate_returns_none() -> None:
    # Default ctor has placeholder slots -> no alternate, no tint -> None.
    sep = PDSeparation()
    assert sep.to_rgb([0.5]) is None


def test_separation_tint_transform_arity_short_returns_none() -> None:
    # Tint produces 1 output but alternate (CMYK) needs 4 -> lite path None.
    sep = _separation(_type2([0.0], [1.0]), alternate="DeviceCMYK")
    assert sep.to_rgb([0.5]) is None


def test_separation_out_of_range_high_tint() -> None:
    # Type-2 with N=1 extrapolates linearly; tint 2.0 -> 2*K clamped by
    # DeviceCMYK to a dark value. Just assert it converts without error.
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    rgb = sep.to_rgb([2.0])
    assert rgb is not None
    assert all(0.0 <= c <= 1.0 for c in rgb)


def test_separation_tint_transform_helper_scales_bytes() -> None:
    # tint_transform: sample 255 -> 1.0 tint -> CMYK(0,0,0,255) ints.
    sep = _separation(_type2([0, 0, 0, 0], [0, 0, 0, 1]))
    alt = [0, 0, 0, 0]
    sep.tint_transform([255.0], alt)
    assert alt == [0, 0, 0, 255]


# ---------- DeviceN: multiple colorants ----------


def test_devicen_two_colorants_cyan() -> None:
    # PostScript {0 0}: stack in = c1 c2 -> out = c1 c2 0 0 (CMYK).
    dn = _devicen(["Cyan", "Magenta"], _type4(b"{ 0 0 }", 2, 4))
    assert _approx(dn.to_rgb([1.0, 0.0]), (0.0, 1.0, 1.0))


def test_devicen_two_colorants_magenta() -> None:
    dn = _devicen(["Cyan", "Magenta"], _type4(b"{ 0 0 }", 2, 4))
    assert _approx(dn.to_rgb([0.0, 1.0]), (1.0, 0.0, 1.0))


def test_devicen_number_of_components_tracks_colorants() -> None:
    dn = _devicen(["A", "B", "C"], _type4(b"{ 0 }", 3, 4))
    assert dn.get_number_of_components() == 3


def test_devicen_initial_color_all_full_tint() -> None:
    # Upstream fills initial with 1.0 per colorant.
    dn = _devicen(["A", "B", "C"], _type4(b"{ 0 }", 3, 4))
    assert dn.get_initial_color().get_components() == [1.0, 1.0, 1.0]


def test_devicen_default_decode_zero_one_per_colorant() -> None:
    dn = _devicen(["A", "B"], _type4(b"{ 0 0 }", 2, 4))
    assert dn.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0]


def test_devicen_colorant_index_lookup() -> None:
    dn = _devicen(["Cyan", "Magenta"], _type4(b"{ 0 0 }", 2, 4))
    assert dn.get_colorant_index("Magenta") == 1
    assert dn.get_colorant_index("Yellow") == -1


def test_devicen_no_tint_transform_returns_none() -> None:
    # Default ctor: empty colorants, placeholder tint -> None.
    dn = PDDeviceN()
    assert dn.to_rgb([]) is None


def test_devicen_attributes_process_component_mapping() -> None:
    # /Attributes /Process maps Cyan->comp0, Magenta->comp1 of DeviceCMYK.
    attrs = COSDictionary()
    proc = COSDictionary()
    proc.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    comps = COSArray()
    comps.add(COSName.get_pdf_name("Cyan"))
    comps.add(COSName.get_pdf_name("Magenta"))
    proc.set_item("Components", comps)
    attrs.set_item("Process", proc)
    dn = _devicen(
        ["Cyan", "Magenta"], _type4(b"{ 0 0 }", 2, 4), attributes=attrs
    )
    assert dn.has_attributes()
    # Cyan tint 1 -> CMYK(1,0,0,0); Magenta 0 -> white; multiply -> cyan.
    assert _approx(dn.to_rgb([1.0, 0.0]), (0.0, 1.0, 1.0))


def test_devicen_attributes_missing_spot_falls_back_to_tint() -> None:
    # /Attributes present but a colorant has no process component and no
    # /Colorants entry -> upstream Altona workaround uses tint transform.
    attrs = COSDictionary()
    proc = COSDictionary()
    proc.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    # Process declares only "Other", so "Spot" is unmapped.
    comps = COSArray()
    comps.add(COSName.get_pdf_name("Other"))
    proc.set_item("Components", comps)
    attrs.set_item("Process", proc)
    dn = _devicen(
        ["Spot"], _type4(b"{ 0 0 0 }", 1, 4), attributes=attrs
    )
    # Tint transform {0 0 0}: in=t -> out=t 0 0 0 -> CMYK cyan ramp.
    assert _approx(dn.to_rgb([1.0]), (0.0, 1.0, 1.0))


def test_devicen_to_raw_image_is_none() -> None:
    # Upstream PDDeviceN.toRawImage unconditionally returns null.
    dn = _devicen(["A", "B"], _type4(b"{ 0 0 }", 2, 4))
    assert dn.to_raw_image(b"\x00\x00", 1, 1) is None


def test_devicen_subtype_default_is_devicen() -> None:
    dn = _devicen(["A"], _type4(b"{ 0 0 0 }", 1, 4))
    assert dn.get_subtype() == "DeviceN"
    assert dn.is_n_channel() is False


# ---------- ICCBased: N-component fallback ----------


@pytest.mark.parametrize(
    ("n", "expected_alt"),
    [(1, "DeviceGray"), (3, "DeviceRGB"), (4, "DeviceCMYK")],
)
def test_iccbased_n_fallback_alternate(n: int, expected_alt: str) -> None:
    icc = _iccbased(n)
    alt = icc.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == expected_alt


def test_iccbased_invalid_n_no_alternate_is_none() -> None:
    # N=2 is not in {1,3,4} and no /Alternate -> permissive None.
    icc = _iccbased(2)
    assert icc.get_alternate_color_space() is None


def test_iccbased_components_track_n() -> None:
    assert _iccbased(1).get_number_of_components() == 1
    assert _iccbased(3).get_number_of_components() == 3
    assert _iccbased(4).get_number_of_components() == 4


def test_iccbased_initial_color_gray_zeros() -> None:
    # No profile, N=1 -> DeviceGray alternate -> initial [0.0].
    assert _iccbased(1).get_initial_color().get_components() == [0.0]


def test_iccbased_initial_color_rgb_zeros() -> None:
    assert _iccbased(3).get_initial_color().get_components() == [0.0, 0.0, 0.0]


def test_iccbased_initial_color_cmyk_is_black() -> None:
    # DeviceCMYK initial color is (0,0,0,1) (K=1 black) -> mirrors upstream
    # fallbackToAlternateColorSpace -> alternateColorSpace.getInitialColor().
    assert _iccbased(4).get_initial_color().get_components() == [
        0.0,
        0.0,
        0.0,
        1.0,
    ]


def test_iccbased_to_rgb_via_n_fallback_cmyk_black() -> None:
    # CMYK (0,0,0,1) -> black through the DeviceCMYK fallback.
    assert _approx(_iccbased(4).to_rgb([0.0, 0.0, 0.0, 1.0]), (0.0, 0.0, 0.0))


def test_iccbased_to_rgb_via_n_fallback_cmyk_white() -> None:
    assert _approx(_iccbased(4).to_rgb([0.0, 0.0, 0.0, 0.0]), (1.0, 1.0, 1.0))


def test_iccbased_to_rgb_via_n_fallback_gray() -> None:
    # DeviceGray 0.5 -> mid gray.
    assert _approx(_iccbased(1).to_rgb([0.5]), (0.5, 0.5, 0.5))


def test_iccbased_explicit_alternate_overrides_n() -> None:
    # /Alternate DeviceGray on an N=3 ICC overrides the default-by-N synth.
    icc = _iccbased(3, alternate="DeviceGray")
    alt = icc.get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == "DeviceGray"


def test_iccbased_invalid_n_to_rgb_is_none() -> None:
    # N=2, no alternate, no profile -> nothing to convert through.
    assert _iccbased(2).to_rgb([0.5, 0.5]) is None


def test_iccbased_default_decode_zero_one() -> None:
    assert _iccbased(3).get_default_decode(8) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_iccbased_color_space_type_from_n() -> None:
    from pypdfbox.pdmodel.graphics.color.pd_icc_based import (
        TYPE_CMYK,
        TYPE_GRAY,
        TYPE_RGB,
    )

    assert _iccbased(1).get_color_space_type() == TYPE_GRAY
    assert _iccbased(3).get_color_space_type() == TYPE_RGB
    assert _iccbased(4).get_color_space_type() == TYPE_CMYK
    assert _iccbased(2).get_color_space_type() == -1


# ---------- Indexed: lookup-table bounds ----------


def test_indexed_basic_lookup_red_green() -> None:
    idx = _indexed(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0, 0, 255, 0]))
    assert _approx(idx.to_rgb([0.0]), (1.0, 0.0, 0.0))
    assert _approx(idx.to_rgb([1.0]), (0.0, 1.0, 0.0))


def test_indexed_index_above_hival_clamped() -> None:
    # Index 5 > hival 1 -> clamp to last entry (green).
    idx = _indexed(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0, 0, 255, 0]))
    assert _approx(idx.to_rgb([5.0]), (0.0, 1.0, 0.0))


def test_indexed_negative_index_clamped_to_zero() -> None:
    idx = _indexed(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0, 0, 255, 0]))
    assert _approx(idx.to_rgb([-3.0]), (1.0, 0.0, 0.0))


def test_indexed_round_half_up_index() -> None:
    # Math.round(0.5) == 1 (round-half-UP), so 0.5 -> entry 1 (green), NOT
    # Python banker's round(0.5)==0.
    idx = _indexed(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0, 0, 255, 0]))
    assert math.floor(0.5 + 0.5) == 1
    assert _approx(idx.to_rgb([0.5]), (0.0, 1.0, 0.0))


def test_indexed_hival_clamped_at_255_on_read() -> None:
    # get_hival never exceeds 255 (upstream readColorTable: min(hival,255)).
    idx = _indexed(PDDeviceRGB.INSTANCE, 300, bytes([0, 0, 0]))
    assert idx.get_hival() == 255


def test_indexed_truncated_lookup_shrinks_actual_max() -> None:
    # hival 5 promised but only 2 RGB entries' worth of bytes present ->
    # actual_max_index drops to 1.
    idx = _indexed(PDDeviceRGB.INSTANCE, 5, bytes([255, 0, 0, 0, 255, 0]))
    assert idx.get_actual_max_index() == 1


def test_indexed_truncated_lookup_clamps_to_available() -> None:
    idx = _indexed(PDDeviceRGB.INSTANCE, 5, bytes([255, 0, 0, 0, 255, 0]))
    # Index 4 clamped to the last available palette entry (index 1, green).
    assert _approx(idx.to_rgb([4.0]), (0.0, 1.0, 0.0))


def test_indexed_initial_color_is_zero() -> None:
    # Upstream: new PDColor(new float[]{0}, this).
    idx = _indexed(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0, 0, 255, 0]))
    assert idx.get_initial_color().get_components() == [0.0]


def test_indexed_number_of_components_is_one() -> None:
    idx = _indexed(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0, 0, 255, 0]))
    assert idx.get_number_of_components() == 1


def test_indexed_default_decode_index_range() -> None:
    # Indexed default /Decode is [0, 2**bpc - 1], NOT [0, 1].
    idx = _indexed(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0, 0, 255, 0]))
    assert idx.get_default_decode(8) == [0.0, 255.0]
    assert idx.get_default_decode(4) == [0.0, 15.0]
    assert idx.get_default_decode(1) == [0.0, 1.0]


def test_indexed_to_rgb_requires_single_component() -> None:
    idx = _indexed(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0, 0, 255, 0]))
    with pytest.raises(ValueError):
        idx.to_rgb([0.0, 1.0])


def test_indexed_cmyk_base_lookup() -> None:
    # 4-component base; one entry: CMYK (0,0,0,255) -> black.
    idx = _indexed(PDDeviceCMYK.INSTANCE, 0, bytes([0, 0, 0, 255]))
    assert idx.get_base_color_space().get_name() == "DeviceCMYK"
    assert _approx(idx.to_rgb([0.0]), (0.0, 0.0, 0.0))


def test_indexed_gray_base_lookup() -> None:
    # 1-component gray base; entries 0 (black) and 255 (white).
    idx = _indexed(PDDeviceGray.INSTANCE, 1, bytes([0, 255]))
    assert _approx(idx.to_rgb([0.0]), (0.0, 0.0, 0.0))
    assert _approx(idx.to_rgb([1.0]), (1.0, 1.0, 1.0))


def test_indexed_empty_lookup_returns_black() -> None:
    # No palette entries (hival promises 0 but 0 bytes) -> actual_max -1 and
    # to_rgb returns black per pypdfbox's lenient empty-palette path.
    idx = _indexed(PDDeviceRGB.INSTANCE, 0, b"")
    assert idx.get_actual_max_index() == -1
    assert idx.to_rgb([0.0]) == [0.0, 0.0, 0.0]


def test_indexed_create_rejects_short_lookup() -> None:
    # PDIndexed.create validates (hival+1)*components bytes.
    with pytest.raises(ValueError):
        PDIndexed.create(PDDeviceRGB.INSTANCE, 1, bytes([255, 0, 0]))


def test_indexed_create_rejects_hival_over_255() -> None:
    with pytest.raises(ValueError):
        PDIndexed.create(PDDeviceRGB.INSTANCE, 256, bytes([0] * 771))

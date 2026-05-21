"""Wave 1368 round-out tests for ``pypdfbox.pdmodel.graphics.color.pd_separation``.

Targets:

- ``/Colorant``, ``/Alternate``, ``/TintTransform`` round-trip
- placeholder slots → None / has_*() = False
- ``to_rgb`` quantised cache shape (PDSeparation.java line 137)
- ``tint_transform`` mutating-by-reference contract
- ``to_rgb_image`` Lab-fast-path detection (PDFBOX-3622 / 5778)
- ``to_raw_image`` Pillow ``L`` single-band shortcut
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- helpers ----------


def _identity_tint(n_out: int) -> COSDictionary:
    """A type-2 exponential function that returns its single input scaled
    into the output dimensionality (all components carry the same tint)."""
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain = COSArray()
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


def _make_separation(
    colorant: str,
    alternate: PDColorSpace,
    tint: COSDictionary | None = None,
) -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(alternate.get_cos_object())
    arr.add(
        tint
        if tint is not None
        else _identity_tint(alternate.get_number_of_components())
    )
    return PDSeparation(arr)


# ---------- default ctor ----------


def test_default_ctor_placeholder_slots() -> None:
    """A bare PDSeparation has placeholder COSName slots that don't resolve."""
    cs = PDSeparation()
    assert cs.get_colorant_name() == ""
    assert cs.get_alternate_color_space() is None
    assert cs.has_alternate_color_space() is False
    assert cs.get_tint_transform() is None
    assert cs.has_tint_transform() is False


def test_default_initial_color_is_full_tint() -> None:
    cs = PDSeparation()
    initial = cs.get_initial_color()
    assert initial._components == [1.0]


# ---------- colorant name ----------


def test_set_get_colorant_name() -> None:
    cs = PDSeparation()
    cs.set_colorant_name("PANTONE 185 CV")
    assert cs.get_colorant_name() == "PANTONE 185 CV"


# ---------- alternate ----------


def test_alternate_color_space_round_trip() -> None:
    cs = _make_separation("Spot1", PDDeviceRGB.INSTANCE)
    assert cs.get_alternate_color_space() is PDDeviceRGB.INSTANCE
    assert cs.has_alternate_color_space() is True

    cs.set_alternate_color_space(PDDeviceCMYK.INSTANCE)
    assert cs.get_alternate_color_space() is PDDeviceCMYK.INSTANCE


# ---------- tint transform dispatch ----------


def test_tint_transform_resolves_to_pdfunction() -> None:
    cs = _make_separation("Spot1", PDDeviceCMYK.INSTANCE)
    fn = cs.get_tint_transform()
    assert fn is not None
    assert fn.get_function_type() == 2
    assert cs.has_tint_transform() is True


def test_set_tint_transform_accepts_pdfunction_wrapper() -> None:
    cs = _make_separation("Spot1", PDDeviceCMYK.INSTANCE)
    fn = PDFunction.create(_identity_tint(4))
    cs.set_tint_transform(fn)
    assert cs.has_tint_transform() is True


def test_clear_tint_transform_resets_to_placeholder() -> None:
    cs = _make_separation("Spot1", PDDeviceCMYK.INSTANCE)
    assert cs.has_tint_transform()
    cs.clear_tint_transform()
    assert cs.has_tint_transform() is False


def test_set_tint_transform_rejects_non_cos_value() -> None:
    cs = _make_separation("Spot1", PDDeviceCMYK.INSTANCE)
    with pytest.raises(TypeError, match="expects PDFunction or COSBase"):
        cs.set_tint_transform("not-a-function")


# ---------- to_rgb ----------


def test_to_rgb_routes_through_alternate() -> None:
    """Tint 0.5 → alt(0.5)*4 → DeviceCMYK(0.5,0.5,0.5,0.5) → sRGB."""
    cs = _make_separation("Spot1", PDDeviceCMYK.INSTANCE)
    rgb = cs.to_rgb([0.5])
    assert rgb is not None
    r, g, b = rgb
    for c in (r, g, b):
        assert 0.0 <= c <= 1.0


def test_to_rgb_returns_none_without_alternate() -> None:
    cs = PDSeparation()
    assert cs.to_rgb([0.5]) is None


def test_to_rgb_caches_quantised_tints() -> None:
    """Repeated calls with the same quantised tint reuse the cache map."""
    cs = _make_separation("Spot1", PDDeviceCMYK.INSTANCE)
    rgb_a = cs.to_rgb([0.5])
    rgb_b = cs.to_rgb([0.5])
    assert rgb_a == rgb_b
    # The cache map exposed for parity assertions.
    assert cs._to_rgb_map is not None
    # int(0.5 * 255) = 127 is the cache key per upstream's quantisation.
    assert 127 in cs._to_rgb_map


# ---------- tint_transform (mutating) ----------


def test_tint_transform_mutates_alt_in_place() -> None:
    cs = _make_separation("Spot1", PDDeviceCMYK.INSTANCE)
    samples = [127.0]
    alt = [0, 0, 0, 0]
    out = cs.tint_transform(samples, alt)
    # The return value IS the populated alt list (idiomatic).
    assert out is alt
    # samples is mutated to [127.0/255 = 0.498...].
    assert abs(samples[0] - 127.0 / 255.0) < 1e-6
    # Identity tint at ~0.5 → all four alt components near 127.
    for v in alt:
        assert 126 <= v <= 128


def test_tint_transform_raises_when_function_missing() -> None:
    cs = PDSeparation()  # default ctor — no tint transform
    with pytest.raises(ValueError, match="requires a tint-transform"):
        cs.tint_transform([127.0], [0, 0, 0, 0])


# ---------- raster: to_rgb_image ----------


def test_to_rgb_image_with_devicergb_alternate() -> None:
    """The standard tint-transform raster path for non-Lab alternates."""
    cs = _make_separation("Spot1", PDDeviceRGB.INSTANCE)
    # 4 pixels, tint = 0 / 127 / 255 / 0.
    raster = b"\x00\x7f\xff\x00"
    img = cs.to_rgb_image(raster, 2, 2)
    assert img.size == (2, 2)
    assert img.mode == "RGB"


def test_to_rgb_image_dispatches_to_lab_path_when_alternate_is_lab() -> None:
    """PDFBOX-3622: Lab alternates must use the to_rgb_image2 path."""
    lab = PDLab()
    cs = _make_separation("Spot1", lab, tint=_identity_tint(3))
    # Force into to_rgb_image2 by giving Lab alternate.
    img = cs.to_rgb_image(b"\x00\x7f\xff\x00", 2, 2)
    assert img.size == (2, 2)
    assert img.mode == "RGB"


def test_to_rgb_image2_without_alternate_falls_through_or_raises() -> None:
    """Without an alternate, ``to_rgb_image2`` falls through to the base
    PDColorSpace.to_rgb_image path, which raises NotImplementedError for
    a default Separation (the underlying ``PDColor.to_rgb`` cannot route
    a tint sample without an alternate). This matches upstream's
    behaviour of treating a malformed Separation as renderer-unrecoverable.
    """
    cs = PDSeparation()
    with pytest.raises(NotImplementedError):
        cs.to_rgb_image2(b"\x00", 1, 1)


# ---------- raster: to_raw_image ----------


def test_to_raw_image_returns_single_band_L_image() -> None:
    cs = _make_separation("Spot1", PDDeviceRGB.INSTANCE)
    img = cs.to_raw_image(b"\x00\x7f\xff\x00", 2, 2)
    assert img.size == (2, 2)
    assert img.mode == "L"
    pixels = list(img.getdata())
    assert pixels == [0, 0x7F, 0xFF, 0]


def test_to_raw_image_pads_short_raster() -> None:
    cs = _make_separation("Spot1", PDDeviceRGB.INSTANCE)
    # 2 bytes for a 2x2 = 4-pixel image — pad with zeros.
    img = cs.to_raw_image(b"\xff\xff", 2, 2)
    pixels = list(img.getdata())
    assert pixels == [0xFF, 0xFF, 0, 0]


# ---------- default decode ----------


def test_default_decode_is_unit_pair() -> None:
    cs = _make_separation("Spot1", PDDeviceCMYK.INSTANCE)
    assert cs.get_default_decode(8) == [0.0, 1.0]


# ---------- string form ----------


def test_to_string_format() -> None:
    cs = _make_separation("Spot1", PDDeviceRGB.INSTANCE)
    s = cs.to_string()
    assert s.startswith("Separation{")
    assert "Spot1" in s
    assert "DeviceRGB" in s


# ---------- raster: ICCBased(Lab) alternate routes through Lab path ----------


def test_to_rgb_image_dispatches_lab_when_iccbased_wraps_lab() -> None:
    """PDFBOX-5778: ICCBased whose alternate is Lab should pick the Lab path."""
    # Build a PDICCBased manually with Lab as its /Alternate.
    from pypdfbox.cos import COSStream

    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("N"), 3)
    lab = PDLab()
    stream.set_item(COSName.get_pdf_name("Alternate"), lab.get_cos_object())
    icc_arr = COSArray()
    icc_arr.add(COSName.get_pdf_name("ICCBased"))
    icc_arr.add(stream)
    icc = PDICCBased(icc_arr)

    cs = _make_separation("Spot1", icc, tint=_identity_tint(3))
    img = cs.to_rgb_image(b"\x00\x80", 2, 1)
    assert img.size == (2, 1)
    assert img.mode == "RGB"


# ---------- PDColorSpace.create dispatches to Separation ----------


def test_pdcolorspace_create_dispatches_separation_array() -> None:
    cs = _make_separation("Spot1", PDDeviceRGB.INSTANCE)
    arr = cs.get_cos_object()
    dispatched = PDColorSpace.create(arr)
    assert isinstance(dispatched, PDSeparation)
    assert dispatched.get_colorant_name() == "Spot1"

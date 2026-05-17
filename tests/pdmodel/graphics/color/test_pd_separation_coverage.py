"""Coverage-boost tests for
:class:`pypdfbox.pdmodel.graphics.color.pd_separation.PDSeparation`.

Targets the previously-uncovered branches:

- ``set_alternate_color_space`` raising when the alternate has no COS form
  (line 100).
- ``set_tint_transform`` rejecting a PDFunction-like wrapper whose
  ``get_cos_object()`` returns ``None`` (line 153), the bare-COSBase fall
  through (line 158), and the non-COS/non-PDFunction TypeError (lines
  159-163).
- ``to_rgb`` returning ``None`` when ``PDColor.to_rgb`` itself returns
  ``None`` (line 213), and the cache hit on a second call (line 209).
- ``tint_transform`` raising when no function is set (line 239).
- ``to_rgb_image`` super-fallback when no alternate is set (line 271),
  the ``PDLab`` short-circuit (line 274), the ``PDICCBased`` wrapping a
  ``PDLab`` alternate short-circuit (lines 276-278), and the short-raster
  zero-pad (line 286).
- ``to_rgb_image2`` super-fallback paths (lines 322-327) and the
  ``alternate.to_rgb`` returning ``None`` branch (lines 344-346).
- ``to_raw_image`` short-raster zero-pad (line 376).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.common.function import PDFunction
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- helpers ----------


def _make_tint_function_type2(n_outputs: int = 3) -> COSDictionary:
    """Build a Type 2 function dictionary mapping ``[0, 1]`` to ``n_outputs``
    components. ``C0`` is all zeros and ``C1`` is all ones so the tint
    transform is an identity-style ramp."""
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    domain = COSArray()
    for v in (0.0, 1.0):
        domain.add(COSFloat(v))
    d.set_item("Domain", domain)
    c0 = COSArray()
    for _ in range(n_outputs):
        c0.add(COSFloat(0.0))
    d.set_item("C0", c0)
    c1 = COSArray()
    for _ in range(n_outputs):
        c1.add(COSFloat(1.0))
    d.set_item("C1", c1)
    d.set_int("N", 1)
    return d


def _make_pd_function_type2(n_outputs: int = 3) -> PDFunction:
    fn = PDFunction.create(_make_tint_function_type2(n_outputs))
    assert fn is not None
    return fn


class _CosLessColorSpace(PDColorSpace):
    """A color space whose ``get_cos_object`` returns ``None``. Used to
    exercise the ``set_alternate_color_space`` TypeError branch."""

    def __init__(self) -> None:  # noqa: D401 - test fixture
        # Skip super().__init__ to keep _array unset.
        pass

    def get_name(self) -> str:
        return "Bogus"

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self):  # type: ignore[override]
        return None

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        return [0.0, 1.0]

    def get_cos_object(self):  # type: ignore[override]
        return None


class _CosLessFunction:
    """A duck-typed PDFunction substitute whose ``get_cos_object`` returns
    ``None`` — used to verify ``set_tint_transform``'s TypeError branch."""

    def get_cos_object(self):  # noqa: D401 - test fixture
        return None


# ---------- set_alternate_color_space error path ----------


def test_set_alternate_color_space_raises_when_cos_none() -> None:
    cs = PDSeparation()
    with pytest.raises(TypeError):
        cs.set_alternate_color_space(_CosLessColorSpace())


# ---------- set_tint_transform branches ----------


def test_set_tint_transform_pd_function_with_none_cos_raises() -> None:
    cs = PDSeparation()
    with pytest.raises(TypeError):
        cs.set_tint_transform(_CosLessFunction())


def test_set_tint_transform_accepts_raw_cos_base() -> None:
    cs = PDSeparation()
    raw = _make_tint_function_type2(1)
    cs.set_tint_transform(raw)
    assert cs.get_tint_transform_cos() is raw


def test_set_tint_transform_rejects_non_cos_non_function() -> None:
    cs = PDSeparation()
    with pytest.raises(TypeError):
        cs.set_tint_transform(42)


def test_set_tint_transform_accepts_pd_function() -> None:
    cs = PDSeparation()
    fn = _make_pd_function_type2(1)
    cs.set_tint_transform(fn)
    assert cs.get_tint_transform_cos() is fn.get_cos_object()


# ---------- to_rgb cache + None propagation ----------


def test_to_rgb_caches_results() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(1))
    first = cs.to_rgb([0.5])
    second = cs.to_rgb([0.5])
    assert first == second
    # Cache populated after first call.
    assert cs._to_rgb_map is not None  # noqa: SLF001
    assert 127 in cs._to_rgb_map  # noqa: SLF001


def test_to_rgb_returns_none_when_no_alternate() -> None:
    cs = PDSeparation()
    cs.set_tint_transform(_make_tint_function_type2(1))
    # Alternate slot is the default empty-name placeholder => create returns None.
    assert cs.to_rgb([0.5]) is None


def test_to_rgb_returns_none_when_no_function() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    # No tint transform => get_tint_transform returns None.
    assert cs.to_rgb([0.5]) is None


def test_to_rgb_returns_none_when_pd_color_to_rgb_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(1))
    # Force PDColor.to_rgb to return None so we hit the
    # ``if result is None: return None`` branch.
    from pypdfbox.pdmodel.graphics.color import pd_color as pd_color_mod
    from pypdfbox.pdmodel.graphics.color import pd_separation as pd_sep_mod

    monkeypatch.setattr(
        pd_sep_mod.PDColor,
        "to_rgb",
        lambda self: None,
    )
    # Re-import sanity — we patched on the symbol PDSeparation.to_rgb uses.
    _ = pd_color_mod  # silence unused
    assert cs.to_rgb([0.25]) is None


# ---------- tint_transform helper ----------


def test_tint_transform_raises_without_function() -> None:
    cs = PDSeparation()
    with pytest.raises(ValueError, match="tint_transform"):
        cs.tint_transform([128.0], [0, 0, 0])


def test_tint_transform_scales_and_writes_output() -> None:
    cs = PDSeparation()
    cs.set_tint_transform(_make_tint_function_type2(3))
    samples = [255.0]
    alt = [0, 0, 0]
    result = cs.tint_transform(samples, alt)
    # Identity ramp (C0=0, C1=1, N=1) — 255 / 255 = 1.0 -> [255, 255, 255].
    assert result == [255, 255, 255]
    assert alt == [255, 255, 255]
    # samples mutated in place: scaled by 255.
    assert samples[0] == pytest.approx(1.0)


# ---------- to_rgb_image branches ----------


def test_to_rgb_image_super_when_no_alternate_raises_via_pdcolor() -> None:
    # When no alternate is set, ``to_rgb_image`` falls through to
    # ``super().to_rgb_image`` (line 271) which ultimately invokes
    # ``PDColor.to_rgb`` on a Separation without an underlying CS —
    # which raises NotImplementedError. That's the documented behaviour
    # for the unconfigured separation case.
    cs = PDSeparation()
    with pytest.raises(NotImplementedError):
        cs.to_rgb_image(b"\x00\x80\xff\x40", 2, 2)


def test_to_rgb_image_short_raster_is_zero_padded() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(1))
    # Pass 1 byte for a 2x2 raster -> pads to 4 bytes (3 zero pad).
    img = cs.to_rgb_image(b"\xff", 2, 2)
    assert img.mode == "RGB"
    assert img.size == (2, 2)


def test_to_rgb_image_lab_alternate_short_circuits_to_rgb_image2() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDLab())
    cs.set_tint_transform(_make_tint_function_type2(3))
    img = cs.to_rgb_image(b"\x00\xff\x80\x40", 2, 2)
    # rgb_image2 path returns a PIL ``RGB`` image directly.
    assert img.mode == "RGB"
    assert img.size == (2, 2)


def test_to_rgb_image_icc_wrapping_lab_alternate_short_circuits() -> None:
    cs = PDSeparation()
    icc = PDICCBased()
    icc.set_alternate(PDLab())
    cs.set_alternate_color_space(icc)
    cs.set_tint_transform(_make_tint_function_type2(3))
    img = cs.to_rgb_image(b"\x10\x20\x30\x40", 2, 2)
    assert img.mode == "RGB"
    assert img.size == (2, 2)


def test_to_rgb_image_icc_non_lab_alternate_uses_default_path() -> None:
    cs = PDSeparation()
    icc = PDICCBased()
    icc.set_alternate(PDDeviceGray.INSTANCE)
    cs.set_alternate_color_space(icc)
    cs.set_tint_transform(_make_tint_function_type2(icc.get_number_of_components()))
    img = cs.to_rgb_image(b"\x00\xff\x80\x40", 2, 2)
    assert img.mode == "RGB"
    assert img.size == (2, 2)


def test_to_rgb_image_device_gray_alternate_round_trip() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(1))
    img = cs.to_rgb_image(b"\x00\x80\xff\x40", 2, 2)
    assert img.mode == "RGB"
    assert img.size == (2, 2)


# ---------- to_rgb_image2 branches ----------


def test_to_rgb_image2_super_when_no_alternate_raises_via_pdcolor() -> None:
    # Mirrors the to_rgb_image super fallback — without an alternate
    # ``to_rgb_image2`` defers to base ``to_rgb_image`` which can't
    # rasterise a placeholder Separation.
    cs = PDSeparation()
    with pytest.raises(NotImplementedError):
        cs.to_rgb_image2(b"\x00\x80\xff\x40", 2, 2)


def test_to_rgb_image2_super_when_no_function_raises_via_pdcolor() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    # Alternate set but no tint transform -> super() path hits PDColor.to_rgb
    # on Separation which still has no tint function -> NotImplementedError.
    with pytest.raises(NotImplementedError):
        cs.to_rgb_image2(b"\x00\xff", 2, 1)


def test_to_rgb_image2_handles_none_to_rgb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(1))
    # Force the alternate's to_rgb to return None -> rgb cache lands on (0, 0, 0).
    monkeypatch.setattr(
        PDDeviceGray,
        "to_rgb",
        lambda self, value: None,
    )
    img = cs.to_rgb_image2(b"\x80", 1, 1)
    assert img.mode == "RGB"
    # Single black pixel.
    assert img.getpixel((0, 0)) == (0, 0, 0)


def test_to_rgb_image2_short_raster_is_zero_padded() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(1))
    img = cs.to_rgb_image2(b"", 2, 2)
    assert img.mode == "RGB"
    assert img.size == (2, 2)


def test_to_rgb_image2_uses_cache_for_repeated_samples() -> None:
    cs = PDSeparation()
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(1))
    # All four pixels share the same sample -> cache hit on 2nd/3rd/4th.
    img = cs.to_rgb_image2(b"\x80\x80\x80\x80", 2, 2)
    px = img.getpixel((0, 0))
    assert img.getpixel((1, 0)) == px
    assert img.getpixel((0, 1)) == px
    assert img.getpixel((1, 1)) == px


# ---------- to_raw_image branches ----------


def test_to_raw_image_returns_l_mode() -> None:
    cs = PDSeparation()
    img = cs.to_raw_image(b"\x00\x80\xff\x40", 2, 2)
    assert img.mode == "L"
    assert img.size == (2, 2)
    # Untouched 8-bit data.
    assert list(img.getdata()) == [0, 128, 255, 64]


def test_to_raw_image_short_raster_is_zero_padded() -> None:
    cs = PDSeparation()
    img = cs.to_raw_image(b"\x10", 2, 2)
    assert img.mode == "L"
    assert img.size == (2, 2)
    assert list(img.getdata()) == [16, 0, 0, 0]


# ---------- sanity coverage of accessors not yet asserted elsewhere ----------


def test_str_contains_colorant_alternate_and_tint() -> None:
    cs = PDSeparation()
    cs.set_colorant_name("PANTONE 185 C")
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(3))
    rendered = str(cs)
    assert rendered.startswith("Separation{")
    assert "PANTONE 185 C" in rendered
    assert "DeviceRGB" in rendered


def test_to_string_matches_dunder_str() -> None:
    cs = PDSeparation()
    cs.set_colorant_name("Spot1")
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    cs.set_tint_transform(_make_tint_function_type2(1))
    assert cs.to_string() == str(cs)


def test_str_handles_missing_alternate_and_tint() -> None:
    cs = PDSeparation()
    rendered = str(cs)
    # Default placeholders -> colorant="", alternate=None, tint=None.
    assert "None" in rendered


def test_has_alternate_color_space_reflects_population() -> None:
    cs = PDSeparation()
    assert cs.has_alternate_color_space() is False
    cs.set_alternate_color_space(PDDeviceGray.INSTANCE)
    assert cs.has_alternate_color_space() is True


def test_has_tint_transform_reflects_population() -> None:
    cs = PDSeparation()
    assert cs.has_tint_transform() is False
    cs.set_tint_transform(_make_tint_function_type2(1))
    assert cs.has_tint_transform() is True


def test_clear_tint_transform_restores_placeholder() -> None:
    cs = PDSeparation()
    cs.set_tint_transform(_make_tint_function_type2(1))
    assert cs.has_tint_transform() is True
    cs.clear_tint_transform()
    assert cs.has_tint_transform() is False


def test_get_tint_transform_returns_none_for_placeholder() -> None:
    cs = PDSeparation()
    assert cs.get_tint_transform() is None


def test_get_tint_transform_returns_none_for_invalid_function() -> None:
    cs = PDSeparation()
    # Stuff a function dictionary with an unsupported /FunctionType -> PDFunction.create
    # raises ValueError, which the try/except in get_tint_transform swallows.
    bad = COSDictionary()
    bad.set_int("FunctionType", 99)
    cs.set_tint_transform(bad)
    assert cs.get_tint_transform() is None


def test_get_default_decode_is_zero_one() -> None:
    assert PDSeparation().get_default_decode(8) == [0.0, 1.0]


def test_get_colorant_name_returns_none_for_non_name_entry() -> None:
    cs = PDSeparation()
    # Stuff a non-COSName at the colorant index.
    cs._array.set(1, COSDictionary())  # noqa: SLF001
    assert cs.get_colorant_name() is None


def test_get_array_object_returns_none_when_out_of_range() -> None:
    cs = PDSeparation()
    # Default array has 4 slots (0..3). Index 99 -> None.
    assert cs._get_array_object(99) is None  # noqa: SLF001


def test_ensure_array_size_grows_with_placeholders() -> None:
    cs = PDSeparation()
    cs._ensure_array_size(10)  # noqa: SLF001
    assert cs._array.size() >= 10  # noqa: SLF001
    # Newly-added entries are empty COSName placeholders.
    assert isinstance(cs._array.get_object(7), COSName)  # noqa: SLF001


def test_get_initial_color_is_full_tint() -> None:
    # Covers ``get_initial_color`` accessor — returns the cached PDColor.
    cs = PDSeparation()
    assert cs.get_initial_color().get_components() == [1.0]


def test_get_alternate_color_space_returns_none_for_missing_slot() -> None:
    # Build a Separation array missing the alternate-CS slot entirely
    # so ``_get_array_object`` returns ``None`` and the early-return
    # branch fires (line 92).
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("Spot1"))
    # Stop short — no alternate-CS, no tint transform slot.
    cs = PDSeparation(arr)
    assert cs.get_alternate_color_space() is None


def test_get_tint_transform_returns_none_when_cos_is_none() -> None:
    # Mirror the line-121 branch via a Separation array missing the
    # tint-transform slot.
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("Spot1"))
    arr.add(COSName.get_pdf_name("DeviceGray"))
    cs = PDSeparation(arr)
    assert cs.get_tint_transform() is None


def test_set_tint_transform_with_raw_cos_base_stores_unchanged() -> None:
    # Covers the ``isinstance(transform, COSBase)`` branch (line 158) —
    # raw COSName goes straight in without unwrapping.
    cs = PDSeparation()
    name = COSName.get_pdf_name("Identity")
    cs.set_tint_transform(name)
    assert cs.get_tint_transform_cos() is name

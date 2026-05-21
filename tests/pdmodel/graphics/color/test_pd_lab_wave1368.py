"""Wave 1368 round-out tests for ``pypdfbox.pdmodel.graphics.color.pd_lab``.

Targets:

- ``/WhitePoint``, ``/BlackPoint``, ``/Range`` round-trip
- a*/b* per-component range accessors + reset-to-defaults
- ``inverse`` static helper (PDF 32000-1 §8.6.5.4 piecewise companding)
- ``to_rgb`` sanity (D65 + custom whitepoint) and rejection of short inputs
- ``get_default_range_array`` static helper
- ``get_default_decode`` derives /Range bounds for image XObjects
- ``to_raw_image`` returns ``None`` (no native Pillow analogue)
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab

# ---------- defaults ----------


def test_default_whitepoint_is_unit_tristimulus() -> None:
    cs = PDLab()
    assert cs.get_white_point() == [1.0, 1.0, 1.0]
    assert cs.is_white_point() is True


def test_default_blackpoint_is_zero_tristimulus() -> None:
    cs = PDLab()
    assert cs.get_black_point() == [0.0, 0.0, 0.0]
    assert cs.has_black_point() is False


def test_default_range_is_minus_100_to_100_for_a_and_b() -> None:
    cs = PDLab()
    assert cs.get_range() == [-100.0, 100.0, -100.0, 100.0]
    assert cs.has_range() is False
    assert cs.get_a_range() == (-100.0, 100.0)
    assert cs.get_b_range() == (-100.0, 100.0)


def test_initial_color_uses_clamped_a_b_minimums() -> None:
    cs = PDLab()
    initial = cs.get_initial_color()
    # L=0, a=max(0, a_min)=0, b=max(0, b_min)=0.
    assert initial._components == [0.0, 0.0, 0.0]


def test_initial_color_reflects_positive_range_minimum() -> None:
    cs = PDLab()
    # Force a positive a* minimum — initial color should track it.
    cs.set_range([5.0, 10.0, 7.0, 12.0])
    initial = cs.get_initial_color()
    comps = initial._components
    assert math.isclose(comps[0], 0.0, abs_tol=1e-6)
    assert math.isclose(comps[1], 5.0, abs_tol=1e-5)
    assert math.isclose(comps[2], 7.0, abs_tol=1e-5)


# ---------- whitepoint / blackpoint ----------


def test_set_whitepoint_round_trip() -> None:
    cs = PDLab()
    cs.set_white_point([0.9505, 1.0, 1.089])
    wp = cs.get_white_point()
    # COSFloat stores at 32-bit precision — compare approximately.
    assert math.isclose(wp[0], 0.9505, abs_tol=1e-6)
    assert math.isclose(wp[1], 1.0, abs_tol=1e-6)
    assert math.isclose(wp[2], 1.089, abs_tol=1e-6)
    assert cs.has_white_point() is True
    # Non-unit whitepoint should NOT register as the calibration-skip
    # shortcut.
    assert cs.is_white_point() is False


def test_set_blackpoint_round_trip() -> None:
    cs = PDLab()
    cs.set_black_point([0.1, 0.2, 0.3])
    bp = cs.get_black_point()
    assert math.isclose(bp[0], 0.1, abs_tol=1e-6)
    assert math.isclose(bp[1], 0.2, abs_tol=1e-6)
    assert math.isclose(bp[2], 0.3, abs_tol=1e-6)
    assert cs.has_black_point() is True


def test_clear_blackpoint_returns_to_zero_default() -> None:
    cs = PDLab()
    cs.set_black_point([0.5, 0.5, 0.5])
    cs.clear_black_point()
    assert cs.has_black_point() is False
    assert cs.get_black_point() == [0.0, 0.0, 0.0]


# ---------- /Range component-level access ----------


def test_set_a_range_updates_first_pair_only() -> None:
    cs = PDLab()
    cs.set_a_range((-50.0, 50.0))
    assert cs.get_a_range() == (-50.0, 50.0)
    assert cs.get_b_range() == (-100.0, 100.0)


def test_set_b_range_updates_second_pair_only() -> None:
    cs = PDLab()
    cs.set_b_range((-25.0, 25.0))
    assert cs.get_a_range() == (-100.0, 100.0)
    assert cs.get_b_range() == (-25.0, 25.0)


def test_set_a_range_none_resets_to_default() -> None:
    cs = PDLab()
    cs.set_a_range((-50.0, 50.0))
    cs.set_a_range(None)
    assert cs.get_a_range() == (-100.0, 100.0)


def test_set_b_range_none_resets_to_default() -> None:
    cs = PDLab()
    cs.set_b_range((-25.0, 25.0))
    cs.set_b_range(None)
    assert cs.get_b_range() == (-100.0, 100.0)


def test_clear_range_returns_defaults() -> None:
    cs = PDLab()
    cs.set_range([10.0, 20.0, 30.0, 40.0])
    cs.clear_range()
    assert cs.has_range() is False
    assert cs.get_range() == [-100.0, 100.0, -100.0, 100.0]


def test_set_component_range_array_alias() -> None:
    """Public alias of ``_set_component_range`` mirrors upstream private name."""
    cs = PDLab()
    cs.set_component_range_array((0.0, 50.0), 0)  # a* slot
    assert cs.get_a_range() == (0.0, 50.0)
    cs.set_component_range_array((10.0, 90.0), 2)  # b* slot
    assert cs.get_b_range() == (10.0, 90.0)


# ---------- inverse helper ----------


def test_inverse_uses_cubic_branch_above_threshold() -> None:
    """``x > 6/29`` → ``x ** 3``."""
    x = 0.5
    assert math.isclose(PDLab.inverse(x), x * x * x, abs_tol=1e-9)


def test_inverse_uses_affine_branch_below_threshold() -> None:
    """``x <= 6/29`` → ``(108/841) * (x - 4/29)``."""
    x = 0.1
    expected = (108.0 / 841.0) * (x - (4.0 / 29.0))
    assert math.isclose(PDLab.inverse(x), expected, abs_tol=1e-9)


def test_inverse_at_threshold() -> None:
    """At the threshold the cubic branch fires (strict ``>``)."""
    x = 6.0 / 29.0
    expected = (108.0 / 841.0) * (x - (4.0 / 29.0))
    assert math.isclose(PDLab.inverse(x), expected, abs_tol=1e-9)


# ---------- to_rgb ----------


def test_to_rgb_white_lab_returns_high_srgb() -> None:
    """L=100 with unit whitepoint produces a clamped near-white sRGB.

    The exact channels depend on the IEC 61966-2-1 sRGB matrix applied
    to ``XYZ = (1, 1, 1)`` — that XYZ is brighter than the D65 white
    point so R and B saturate at 1.0 and G lands around 0.95. We assert
    on the brightness floor, not exact equality.
    """
    cs = PDLab()
    rgb = cs.to_rgb([100.0, 0.0, 0.0])
    assert rgb is not None
    r, g, b = rgb
    assert r >= 0.9
    assert g >= 0.9
    assert b >= 0.9


def test_to_rgb_black_lab_returns_black_srgb() -> None:
    cs = PDLab()
    rgb = cs.to_rgb([0.0, 0.0, 0.0])
    assert rgb is not None
    r, g, b = rgb
    # Lab origin maps to (0, 0, 0) in sRGB.
    assert r == 0.0
    assert g == 0.0
    assert b == 0.0


def test_to_rgb_custom_whitepoint_scales_xyz() -> None:
    """A custom whitepoint scales the XYZ outputs accordingly."""
    cs = PDLab()
    cs.set_white_point([0.5, 0.5, 0.5])
    rgb_custom = cs.to_rgb([50.0, 0.0, 0.0])
    cs2 = PDLab()
    rgb_unit = cs2.to_rgb([50.0, 0.0, 0.0])
    # Scaled whitepoint → lower XYZ → darker sRGB.
    assert rgb_custom is not None and rgb_unit is not None
    assert rgb_custom[1] < rgb_unit[1]


def test_to_rgb_rejects_short_input() -> None:
    cs = PDLab()
    with pytest.raises(ValueError, match="requires three components"):
        cs.to_rgb([1.0])


def test_to_rgb_clamps_negative_xyz_to_zero() -> None:
    """Extreme negative a*/b* should not surface negative sRGB."""
    cs = PDLab()
    rgb = cs.to_rgb([0.0, -200.0, -200.0])
    assert rgb is not None
    for c in rgb:
        assert 0.0 <= c <= 1.0


# ---------- default decode / range helpers ----------


def test_get_default_decode_uses_range_bounds() -> None:
    cs = PDLab()
    cs.set_range([-50.0, 50.0, -25.0, 25.0])
    decode = cs.get_default_decode(8)
    assert decode == [0.0, 100.0, -50.0, 50.0, -25.0, 25.0]


def test_get_default_decode_falls_back_when_range_missing() -> None:
    cs = PDLab()
    decode = cs.get_default_decode(8)
    assert decode == [0.0, 100.0, -100.0, 100.0, -100.0, 100.0]


def test_get_default_range_array_returns_unit_pairs() -> None:
    arr = PDLab.get_default_range_array()
    assert arr.size() == 4
    floats = arr.to_float_array()
    assert floats == [-100.0, 100.0, -100.0, 100.0]


# ---------- to_raw_image ----------


def test_to_raw_image_returns_none() -> None:
    cs = PDLab()
    assert cs.to_raw_image(b"\x00" * 12, 2, 2) is None


# ---------- to_rgb_image sanity ----------


def test_to_rgb_image_returns_pillow_image() -> None:
    cs = PDLab()
    # Solid grey: L=128/255 * 100, a/b at zero crossings.
    raster = b"\x80\x80\x80" * 4
    img = cs.to_rgb_image(raster, 2, 2)
    assert img.size == (2, 2)
    assert img.mode == "RGB"


# ---------- dict accessor errors ----------


def test_dict_accessor_raises_when_array_index_one_wrong() -> None:
    """A malformed Lab array (index 1 is a name) should fail at construction.

    The constructor reads /Range to compute the initial color — this is
    gated by ``_dict()``, so PDLab() with malformed array surfaces the
    error eagerly with a "not a dictionary" message.
    """
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    arr.add(COSName.get_pdf_name("NotADict"))
    with pytest.raises(TypeError, match="not a dictionary"):
        PDLab(arr)


# ---------- dictionary-direct round-trip ----------


def test_setting_via_cos_dictionary_works() -> None:
    """Underlying dictionary mutations are visible through the accessors."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    d = COSDictionary()
    wp = COSArray()
    for v in (0.95, 1.0, 1.09):
        wp.add(COSFloat(v))
    d.set_item(COSName.get_pdf_name("WhitePoint"), wp)
    arr.add(d)
    cs = PDLab(arr)
    out = cs.get_white_point()
    assert math.isclose(out[0], 0.95, abs_tol=1e-6)
    assert math.isclose(out[1], 1.0, abs_tol=1e-6)
    assert math.isclose(out[2], 1.09, abs_tol=1e-6)

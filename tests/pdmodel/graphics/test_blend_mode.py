from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics import BlendMode
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode as BlendModeDirect

# ---------------------------------------------------------------------------
# Re-export & singleton identity
# ---------------------------------------------------------------------------


def test_reexport_from_graphics_package():
    assert BlendMode is BlendModeDirect


def test_singleton_identity_for_each_standard_mode():
    for attr in (
        "NORMAL",
        "MULTIPLY",
        "SCREEN",
        "OVERLAY",
        "DARKEN",
        "LIGHTEN",
        "COLOR_DODGE",
        "COLOR_BURN",
        "HARD_LIGHT",
        "SOFT_LIGHT",
        "DIFFERENCE",
        "EXCLUSION",
        "HUE",
        "SATURATION",
        "COLOR",
        "LUMINOSITY",
    ):
        instance = getattr(BlendMode, attr)
        again = BlendMode.get(instance.get_name())
        assert instance is again, f"{attr} not interned"


def test_compatible_aliases_normal():
    assert BlendMode.COMPATIBLE is BlendMode.NORMAL
    assert BlendMode.get("Compatible") is BlendMode.NORMAL


def test_separable_vs_non_separable_classification():
    for n in (
        "Normal",
        "Multiply",
        "Screen",
        "Overlay",
        "Darken",
        "Lighten",
        "ColorDodge",
        "ColorBurn",
        "HardLight",
        "SoftLight",
        "Difference",
        "Exclusion",
    ):
        bm = BlendMode.get(n)
        assert bm.is_separable()
        assert not bm.is_non_separable()
    for n in ("Hue", "Saturation", "Color", "Luminosity"):
        bm = BlendMode.get(n)
        assert not bm.is_separable()
        assert bm.is_non_separable()


def test_get_cos_name_round_trips():
    assert BlendMode.MULTIPLY.get_cos_name() == COSName.get_pdf_name("Multiply")
    assert BlendMode.LUMINOSITY.get_cos_name() == COSName.get_pdf_name(
        "Luminosity"
    )


def test_repr_and_equality_and_hash():
    a = BlendMode.get("Multiply")
    b = BlendMode.get("Multiply")
    c = BlendMode.get("Screen")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert repr(a) == "BlendMode('Multiply')"


# ---------------------------------------------------------------------------
# Wave 183: STANDARD_NAMES / is_standard / iter_standard / __str__
# ---------------------------------------------------------------------------


def test_standard_names_is_union_of_separable_and_non_separable():
    assert (
        BlendMode.STANDARD_NAMES
        == BlendMode.SEPARABLE_NAMES | BlendMode.NON_SEPARABLE_NAMES
    )


def test_standard_names_has_all_16_modes():
    assert len(BlendMode.STANDARD_NAMES) == 16
    expected = {
        "Normal",
        "Multiply",
        "Screen",
        "Overlay",
        "Darken",
        "Lighten",
        "ColorDodge",
        "ColorBurn",
        "HardLight",
        "SoftLight",
        "Difference",
        "Exclusion",
        "Hue",
        "Saturation",
        "Color",
        "Luminosity",
    }
    assert expected == BlendMode.STANDARD_NAMES


def test_standard_names_is_frozenset():
    assert isinstance(BlendMode.STANDARD_NAMES, frozenset)


def test_standard_names_separable_and_non_separable_disjoint():
    # PDF 32000-1 §11.3.5.1 vs §11.3.5.3 — modes belong to exactly one family.
    assert BlendMode.SEPARABLE_NAMES.isdisjoint(BlendMode.NON_SEPARABLE_NAMES)


def test_is_standard_true_for_each_standard_mode():
    for name in BlendMode.STANDARD_NAMES:
        assert BlendMode.get(name).is_standard(), f"{name} should be standard"


def test_is_standard_false_for_unknown_name():
    bm = BlendMode.get("BogusMode")
    assert bm.is_standard() is False
    # The instance still round-trips its original name on write.
    assert bm.get_name() == "BogusMode"


def test_is_standard_compatible_resolves_to_standard_normal():
    # Compatible interns to the same instance as Normal, which IS standard.
    bm = BlendMode.get("Compatible")
    assert bm is BlendMode.NORMAL
    assert bm.is_standard() is True


def test_iter_standard_yields_all_sixteen_singletons():
    standards = BlendMode.iter_standard()
    assert len(standards) == 16
    # Every entry should be the interned singleton (identity, not equality).
    for bm in standards:
        assert bm is BlendMode.get(bm.get_name())
    # Names should match STANDARD_NAMES exactly.
    assert {bm.get_name() for bm in standards} == BlendMode.STANDARD_NAMES


def test_iter_standard_spec_order_separable_first():
    standards = BlendMode.iter_standard()
    # First 12 are separable (PDF 32000-1 §11.3.5.1).
    for bm in standards[:12]:
        assert bm.is_separable(), f"{bm.get_name()} should be separable"
    # Last 4 are non-separable HSL (§11.3.5.3) in spec order.
    last_four = [bm.get_name() for bm in standards[12:]]
    assert last_four == ["Hue", "Saturation", "Color", "Luminosity"]


def test_iter_standard_first_entry_is_normal():
    assert BlendMode.iter_standard()[0] is BlendMode.NORMAL


def test_str_matches_upstream_to_string_separable():
    # Mirrors upstream BlendMode.toString():
    #   "BlendMode{name=Multiply, isSeparable=true}"
    assert (
        str(BlendMode.MULTIPLY)
        == "BlendMode{name=Multiply, isSeparable=true}"
    )
    assert (
        str(BlendMode.NORMAL) == "BlendMode{name=Normal, isSeparable=true}"
    )


def test_str_matches_upstream_to_string_non_separable():
    assert str(BlendMode.HUE) == "BlendMode{name=Hue, isSeparable=false}"
    assert (
        str(BlendMode.LUMINOSITY)
        == "BlendMode{name=Luminosity, isSeparable=false}"
    )


def test_str_for_unknown_mode_uses_lowercase_false_flag():
    # Unknown modes are non-separable (no per-channel formula registered),
    # so the flag is "false" and the name round-trips verbatim.
    bm = BlendMode.get("BogusMode")
    assert str(bm) == "BlendMode{name=BogusMode, isSeparable=false}"


def test_str_and_repr_are_distinct():
    bm = BlendMode.MULTIPLY
    assert str(bm) != repr(bm)
    assert repr(bm) == "BlendMode('Multiply')"


# ---------------------------------------------------------------------------
# get_instance — the canonical PDFBox API
# ---------------------------------------------------------------------------


def test_get_instance_none_returns_normal():
    assert BlendMode.get_instance(None) is BlendMode.NORMAL


def test_get_instance_cosname_known():
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("Multiply"))
        is BlendMode.MULTIPLY
    )
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("Luminosity"))
        is BlendMode.LUMINOSITY
    )


def test_get_instance_cosname_unknown_falls_back_to_normal():
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("BogusMode"))
        is BlendMode.NORMAL
    )


def test_get_instance_compatible_alias():
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("Compatible"))
        is BlendMode.NORMAL
    )
    assert BlendMode.get_instance("Compatible") is BlendMode.NORMAL


def test_get_instance_str_known_and_unknown():
    assert BlendMode.get_instance("Screen") is BlendMode.SCREEN
    assert BlendMode.get_instance("UnknownMode") is BlendMode.NORMAL


def test_get_instance_array_returns_first_recognised():
    arr = COSArray()
    arr.add(COSName.get_pdf_name("BogusMode"))
    arr.add(COSName.get_pdf_name("Multiply"))
    arr.add(COSName.get_pdf_name("Screen"))
    assert BlendMode.get_instance(arr) is BlendMode.MULTIPLY


def test_get_instance_array_no_match_returns_normal():
    arr = COSArray()
    arr.add(COSName.get_pdf_name("BogusOne"))
    arr.add(COSName.get_pdf_name("BogusTwo"))
    assert BlendMode.get_instance(arr) is BlendMode.NORMAL


def test_get_instance_unsupported_type_returns_normal():
    # A COSDictionary isn't a recognised /BM payload — fall back to Normal.
    assert BlendMode.get_instance(COSDictionary()) is BlendMode.NORMAL


# ---------------------------------------------------------------------------
# from_cos — pre-existing read path, kept for back-compat
# ---------------------------------------------------------------------------


def test_from_cos_none():
    assert BlendMode.from_cos(None) is None


def test_from_cos_name():
    assert (
        BlendMode.from_cos(COSName.get_pdf_name("Multiply"))
        is BlendMode.MULTIPLY
    )


def test_from_cos_array_returns_first_recognised():
    arr = COSArray()
    arr.add(COSName.get_pdf_name("BogusMode"))
    arr.add(COSName.get_pdf_name("Difference"))
    assert BlendMode.from_cos(arr) is BlendMode.DIFFERENCE


def test_from_cos_array_round_trips_unknown_first_when_no_match():
    arr = COSArray()
    arr.add(COSName.get_pdf_name("UnknownOne"))
    arr.add(COSName.get_pdf_name("UnknownTwo"))
    bm = BlendMode.from_cos(arr)
    assert bm is not None
    assert bm.get_name() == "UnknownOne"


# ---------------------------------------------------------------------------
# Per-channel blend formulas (PDF 32000-1 §11.3.5.1 Table 136)
# ---------------------------------------------------------------------------


def test_blend_normal_returns_source():
    assert BlendMode.NORMAL.blend(0.3, 0.7) == pytest.approx(0.3)
    assert BlendMode.NORMAL.blend(0.0, 1.0) == pytest.approx(0.0)
    assert BlendMode.NORMAL.blend(1.0, 0.0) == pytest.approx(1.0)


def test_blend_multiply():
    assert BlendMode.MULTIPLY.blend(0.5, 0.5) == pytest.approx(0.25)
    assert BlendMode.MULTIPLY.blend(1.0, 0.4) == pytest.approx(0.4)
    assert BlendMode.MULTIPLY.blend(0.0, 0.9) == pytest.approx(0.0)


def test_blend_screen():
    # 1 - (1-s)*(1-b)
    assert BlendMode.SCREEN.blend(0.5, 0.5) == pytest.approx(0.75)
    assert BlendMode.SCREEN.blend(0.0, 0.4) == pytest.approx(0.4)
    assert BlendMode.SCREEN.blend(1.0, 0.0) == pytest.approx(1.0)


def test_blend_darken_and_lighten():
    assert BlendMode.DARKEN.blend(0.3, 0.7) == 0.3
    assert BlendMode.DARKEN.blend(0.7, 0.3) == 0.3
    assert BlendMode.LIGHTEN.blend(0.3, 0.7) == 0.7
    assert BlendMode.LIGHTEN.blend(0.7, 0.3) == 0.7


def test_blend_difference_and_exclusion():
    assert BlendMode.DIFFERENCE.blend(0.4, 0.7) == pytest.approx(0.3)
    assert BlendMode.DIFFERENCE.blend(0.9, 0.1) == pytest.approx(0.8)
    # Exclusion: b + s - 2*b*s
    assert BlendMode.EXCLUSION.blend(0.5, 0.5) == pytest.approx(0.5)
    assert BlendMode.EXCLUSION.blend(0.0, 0.0) == pytest.approx(0.0)
    assert BlendMode.EXCLUSION.blend(1.0, 1.0) == pytest.approx(0.0)


def test_blend_hard_light_two_branches():
    # s <= 0.5 → 2*b*s
    assert BlendMode.HARD_LIGHT.blend(0.25, 0.4) == pytest.approx(0.2)
    # s > 0.5 → 1 - 2*(1-b)*(1-s)
    assert BlendMode.HARD_LIGHT.blend(0.75, 0.4) == pytest.approx(0.7)


def test_blend_overlay_is_hard_light_swapped():
    # Overlay(b, s) = HardLight(s, b) per spec.
    s, b = 0.3, 0.6
    assert BlendMode.OVERLAY.blend(s, b) == pytest.approx(
        BlendMode.HARD_LIGHT.blend(b, s)
    )


def test_blend_color_dodge_edges():
    assert BlendMode.COLOR_DODGE.blend(1.0, 0.5) == pytest.approx(1.0)
    assert BlendMode.COLOR_DODGE.blend(0.0, 0.5) == pytest.approx(0.5)
    # b/(1-s) clipped at 1
    assert BlendMode.COLOR_DODGE.blend(0.8, 0.4) == pytest.approx(1.0)


def test_blend_color_burn_edges():
    assert BlendMode.COLOR_BURN.blend(0.0, 0.5) == pytest.approx(0.0)
    assert BlendMode.COLOR_BURN.blend(1.0, 0.5) == pytest.approx(0.5)
    # 1 - min(1, (1-b)/s)
    assert BlendMode.COLOR_BURN.blend(0.5, 0.25) == pytest.approx(
        1.0 - min(1.0, 0.75 / 0.5)
    )


def test_blend_soft_light_known_values():
    # Reference values computed by hand from the spec piecewise formula.
    # Branch 1: s <= 0.5
    s, b = 0.25, 0.5
    expected = b - (1.0 - 2.0 * s) * b * (1.0 - b)
    assert BlendMode.SOFT_LIGHT.blend(s, b) == pytest.approx(expected)
    # Branch 2 with b > 0.25 (sqrt branch)
    s, b = 0.75, 0.5
    expected = b + (2.0 * s - 1.0) * (math.sqrt(b) - b)
    assert BlendMode.SOFT_LIGHT.blend(s, b) == pytest.approx(expected)
    # Branch 2 with b <= 0.25 (polynomial branch)
    s, b = 0.75, 0.2
    d = ((16.0 * b - 12.0) * b + 4.0) * b
    expected = b + (2.0 * s - 1.0) * (d - b)
    assert BlendMode.SOFT_LIGHT.blend(s, b) == pytest.approx(expected)


def test_blend_unknown_mode_falls_back_to_normal():
    bm = BlendMode.get("BogusMode")
    assert bm.blend(0.3, 0.7) == pytest.approx(0.3)


def test_blend_raises_for_non_separable_modes():
    for mode in (
        BlendMode.HUE,
        BlendMode.SATURATION,
        BlendMode.COLOR,
        BlendMode.LUMINOSITY,
    ):
        with pytest.raises(ValueError, match="non-separable"):
            mode.blend(0.5, 0.5)


# ---------------------------------------------------------------------------
# blend_separable_rgb — uniform RGB-triple entry point
# ---------------------------------------------------------------------------


def test_blend_separable_rgb_for_separable_modes():
    src = (0.2, 0.4, 0.6)
    bgd = (0.5, 0.5, 0.5)
    out = BlendMode.MULTIPLY.blend_separable_rgb(src, bgd)
    assert out == pytest.approx((0.1, 0.2, 0.3))


def test_blend_separable_rgb_normal_returns_source_triple():
    src = (0.1, 0.2, 0.3)
    bgd = (0.9, 0.8, 0.7)
    assert BlendMode.NORMAL.blend_separable_rgb(src, bgd) == pytest.approx(src)


def test_blend_separable_rgb_luminosity_replaces_lum():
    # Luminosity = SetLum(Cb, Lum(Cs)). For a grey backdrop the result
    # equals (l, l, l) where l = Lum(Cs).
    src = (1.0, 0.0, 0.0)
    bgd = (0.5, 0.5, 0.5)
    out = BlendMode.LUMINOSITY.blend_separable_rgb(src, bgd)
    expected_lum = 0.30 * 1.0 + 0.59 * 0.0 + 0.11 * 0.0
    assert out == pytest.approx((expected_lum, expected_lum, expected_lum))


def test_blend_separable_rgb_color_preserves_backdrop_lum():
    src = (0.8, 0.2, 0.4)
    bgd = (0.4, 0.4, 0.4)  # grey, lum = 0.4
    r, g, b = BlendMode.COLOR.blend_separable_rgb(src, bgd)
    out_lum = 0.30 * r + 0.59 * g + 0.11 * b
    assert out_lum == pytest.approx(0.4, abs=1e-6)


def test_blend_separable_rgb_hue_picks_source_hue_backdrop_lum():
    # Hue = SetLum(SetSat(Cs, Sat(Cb)), Lum(Cb)).
    # Backdrop grey ⇒ Sat(Cb) = 0 ⇒ result is achromatic at Lum(Cb).
    src = (1.0, 0.0, 0.0)
    bgd = (0.4, 0.4, 0.4)
    out = BlendMode.HUE.blend_separable_rgb(src, bgd)
    assert out == pytest.approx((0.4, 0.4, 0.4))


def test_blend_separable_rgb_saturation_zero_when_source_grey():
    # Saturation = SetLum(SetSat(Cb, Sat(Cs)), Lum(Cb)).
    # Source grey ⇒ Sat(Cs) = 0 ⇒ result is achromatic at Lum(Cb).
    src = (0.7, 0.7, 0.7)
    bgd = (0.8, 0.2, 0.4)
    out = BlendMode.SATURATION.blend_separable_rgb(src, bgd)
    bgd_lum = 0.30 * 0.8 + 0.59 * 0.2 + 0.11 * 0.4
    assert out == pytest.approx((bgd_lum, bgd_lum, bgd_lum))


# ---------------------------------------------------------------------------
# is_separable_blend_mode (upstream-named alias of is_separable)
# ---------------------------------------------------------------------------


def test_is_separable_blend_mode_aliases_is_separable_for_separable_modes():
    for mode in (
        BlendMode.NORMAL,
        BlendMode.MULTIPLY,
        BlendMode.SCREEN,
        BlendMode.OVERLAY,
        BlendMode.DARKEN,
        BlendMode.LIGHTEN,
        BlendMode.COLOR_DODGE,
        BlendMode.COLOR_BURN,
        BlendMode.HARD_LIGHT,
        BlendMode.SOFT_LIGHT,
        BlendMode.DIFFERENCE,
        BlendMode.EXCLUSION,
    ):
        assert mode.is_separable_blend_mode() is True
        assert mode.is_separable_blend_mode() == mode.is_separable()


def test_is_separable_blend_mode_false_for_non_separable_modes():
    for mode in (
        BlendMode.HUE,
        BlendMode.SATURATION,
        BlendMode.COLOR,
        BlendMode.LUMINOSITY,
    ):
        assert mode.is_separable_blend_mode() is False
        assert mode.is_separable_blend_mode() == mode.is_separable()


def test_is_separable_blend_mode_false_for_unknown_name():
    assert BlendMode.get("WeirdNonStandard").is_separable_blend_mode() is False


# ---------------------------------------------------------------------------
# get_blend_channel_function (upstream parity helper)
# ---------------------------------------------------------------------------


def test_get_blend_channel_function_returns_callable_for_separable_modes():
    fn = BlendMode.MULTIPLY.get_blend_channel_function()
    assert fn is not None
    # Multiply: src * dest.
    assert fn(0.5, 0.4) == pytest.approx(0.2)
    # Equivalent to .blend(src, dest).
    assert fn(0.3, 0.7) == BlendMode.MULTIPLY.blend(0.3, 0.7)


def test_get_blend_channel_function_normal_returns_identity_in_source():
    fn = BlendMode.NORMAL.get_blend_channel_function()
    assert fn is not None
    assert fn(0.42, 0.99) == pytest.approx(0.42)


def test_get_blend_channel_function_returns_none_for_non_separable_modes():
    for mode in (
        BlendMode.HUE,
        BlendMode.SATURATION,
        BlendMode.COLOR,
        BlendMode.LUMINOSITY,
    ):
        assert mode.get_blend_channel_function() is None


def test_get_blend_channel_function_returns_none_for_unknown_name():
    assert BlendMode.get("UnknownMode").get_blend_channel_function() is None


def test_get_blend_channel_function_matches_blend_for_each_separable_mode():
    sample_pairs = [(0.1, 0.9), (0.3, 0.6), (0.7, 0.2), (0.0, 0.5), (1.0, 0.0)]
    for name in BlendMode.SEPARABLE_NAMES:
        mode = BlendMode.get(name)
        fn = mode.get_blend_channel_function()
        assert fn is not None, name
        for src, dst in sample_pairs:
            assert fn(src, dst) == pytest.approx(mode.blend(src, dst)), name


# ---------------------------------------------------------------------------
# get_blend_function (non-separable RGB blend callable)
# ---------------------------------------------------------------------------


def test_get_blend_function_returns_callable_for_non_separable_modes():
    fn = BlendMode.LUMINOSITY.get_blend_function()
    assert fn is not None
    out = fn(0.4, 0.5, 0.6, 0.2, 0.7, 0.3)
    # Equivalent to .blend_separable_rgb((src), (dest)).
    assert out == BlendMode.LUMINOSITY.blend_separable_rgb(
        (0.4, 0.5, 0.6), (0.2, 0.7, 0.3)
    )


def test_get_blend_function_returns_none_for_separable_modes():
    for mode in (
        BlendMode.NORMAL,
        BlendMode.MULTIPLY,
        BlendMode.OVERLAY,
        BlendMode.HARD_LIGHT,
        BlendMode.SOFT_LIGHT,
    ):
        assert mode.get_blend_function() is None


def test_get_blend_function_returns_none_for_unknown_name():
    assert BlendMode.get("UnknownNonSep").get_blend_function() is None


def test_get_blend_function_one_callable_per_non_separable_mode():
    for name in BlendMode.NON_SEPARABLE_NAMES:
        mode = BlendMode.get(name)
        fn = mode.get_blend_function()
        assert fn is not None, name
        # Every non-separable function accepts the 6-float signature
        # and returns a 3-tuple of floats in [0, 1].
        out = fn(0.3, 0.4, 0.5, 0.6, 0.7, 0.2)
        assert isinstance(out, tuple)
        assert len(out) == 3
        for v in out:
            assert 0.0 <= v <= 1.0 + 1e-9, name


# ---------------------------------------------------------------------------
# Mutual exclusivity: separable XOR non-separable callables
# ---------------------------------------------------------------------------


def test_separable_modes_have_only_channel_function():
    for name in BlendMode.SEPARABLE_NAMES:
        mode = BlendMode.get(name)
        assert mode.get_blend_channel_function() is not None
        assert mode.get_blend_function() is None


def test_non_separable_modes_have_only_blend_function():
    for name in BlendMode.NON_SEPARABLE_NAMES:
        mode = BlendMode.get(name)
        assert mode.get_blend_channel_function() is None
        assert mode.get_blend_function() is not None

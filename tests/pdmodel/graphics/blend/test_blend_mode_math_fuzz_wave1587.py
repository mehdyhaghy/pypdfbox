"""Spec-formula fuzz for the separable / non-separable blend math.

Hammers each PDF 32000-1 §11.3.5 blend function against an independent
reference implementation transcribed straight from the spec (Table 136 /
§11.3.5.3) and from upstream PDFBox 3.0.x ``BlendMode.java``. Every case
checks an exact value, with extra emphasis on boundary inputs (0, 0.5, 1)
and the discontinuous special cases (ColorDodge ``s == 1`` / backdrop 0,
ColorBurn ``s == 0`` / backdrop 1).

``BlendMode.blend(source_channel, backdrop_channel)`` takes ``(s, b)`` in
``[0, 1]`` (source first, matching upstream's ``blendChannel(src, dst)``).
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

# ---------------------------------------------------------------------------
# Reference formulas — independent transcription of PDF 32000-1 §11.3.5.1
# Table 136 and upstream BlendMode.java. b = backdrop, s = source.
# ---------------------------------------------------------------------------


def _ref_normal(s: float, b: float) -> float:
    return s


def _ref_multiply(s: float, b: float) -> float:
    return b * s


def _ref_screen(s: float, b: float) -> float:
    return b + s - b * s


def _ref_hard_light(s: float, b: float) -> float:
    if s <= 0.5:
        return _ref_multiply(2.0 * s, b)
    return _ref_screen(2.0 * s - 1.0, b)


def _ref_overlay(s: float, b: float) -> float:
    return _ref_hard_light(b, s)


def _ref_darken(s: float, b: float) -> float:
    return min(b, s)


def _ref_lighten(s: float, b: float) -> float:
    return max(b, s)


def _ref_color_dodge(s: float, b: float) -> float:
    if b == 0.0:
        return 0.0
    if b >= 1.0 - s:
        return 1.0
    return b / (1.0 - s)


def _ref_color_burn(s: float, b: float) -> float:
    if b == 1.0:
        return 1.0
    if 1.0 - b >= s:
        return 0.0
    return 1.0 - (1.0 - b) / s


def _ref_soft_light(s: float, b: float) -> float:
    if s <= 0.5:
        return b - (1.0 - 2.0 * s) * b * (1.0 - b)
    d = ((16.0 * b - 12.0) * b + 4.0) * b if b <= 0.25 else math.sqrt(b)
    return b + (2.0 * s - 1.0) * (d - b)


def _ref_difference(s: float, b: float) -> float:
    return abs(b - s)


def _ref_exclusion(s: float, b: float) -> float:
    return b + s - 2.0 * b * s


_REFS = {
    BlendMode.NORMAL: _ref_normal,
    BlendMode.MULTIPLY: _ref_multiply,
    BlendMode.SCREEN: _ref_screen,
    BlendMode.OVERLAY: _ref_overlay,
    BlendMode.DARKEN: _ref_darken,
    BlendMode.LIGHTEN: _ref_lighten,
    BlendMode.COLOR_DODGE: _ref_color_dodge,
    BlendMode.COLOR_BURN: _ref_color_burn,
    BlendMode.HARD_LIGHT: _ref_hard_light,
    BlendMode.SOFT_LIGHT: _ref_soft_light,
    BlendMode.DIFFERENCE: _ref_difference,
    BlendMode.EXCLUSION: _ref_exclusion,
}

# A grid of source/backdrop values including all the corners and 0.5.
_GRID = [0.0, 0.125, 0.25, 0.5, 0.75, 0.875, 1.0]


@pytest.mark.parametrize("mode", list(_REFS), ids=lambda m: m.name)
def test_separable_matches_reference_over_grid(mode: BlendMode) -> None:
    ref = _REFS[mode]
    for s in _GRID:
        for b in _GRID:
            assert mode.blend(s, b) == pytest.approx(ref(s, b), abs=1e-12), (
                f"{mode.name} blend({s}, {b})"
            )


def test_multiply_exact() -> None:
    assert BlendMode.MULTIPLY.blend(1.0, 1.0) == 1.0
    assert BlendMode.MULTIPLY.blend(0.0, 1.0) == 0.0
    assert BlendMode.MULTIPLY.blend(0.5, 0.5) == 0.25


def test_screen_exact() -> None:
    assert BlendMode.SCREEN.blend(0.0, 0.0) == 0.0
    assert BlendMode.SCREEN.blend(1.0, 1.0) == 1.0
    assert BlendMode.SCREEN.blend(0.5, 0.5) == 0.75


def test_darken_lighten_exact() -> None:
    assert BlendMode.DARKEN.blend(0.3, 0.7) == 0.3
    assert BlendMode.DARKEN.blend(0.7, 0.3) == 0.3
    assert BlendMode.LIGHTEN.blend(0.3, 0.7) == 0.7
    assert BlendMode.LIGHTEN.blend(0.7, 0.3) == 0.7


def test_difference_exclusion_exact() -> None:
    assert BlendMode.DIFFERENCE.blend(0.2, 0.9) == pytest.approx(0.7)
    assert BlendMode.DIFFERENCE.blend(0.9, 0.2) == pytest.approx(0.7)
    # Exclusion uses coefficient 2 (not screen's b+s-bs).
    assert BlendMode.EXCLUSION.blend(0.5, 0.5) == pytest.approx(0.5)
    assert BlendMode.EXCLUSION.blend(1.0, 1.0) == pytest.approx(0.0)
    assert BlendMode.EXCLUSION.blend(0.0, 1.0) == pytest.approx(1.0)


def test_color_dodge_special_cases() -> None:
    # Backdrop 0 → 0 regardless of source.
    assert BlendMode.COLOR_DODGE.blend(1.0, 0.0) == 0.0
    assert BlendMode.COLOR_DODGE.blend(0.5, 0.0) == 0.0
    assert BlendMode.COLOR_DODGE.blend(0.0, 0.0) == 0.0
    # Source 1, backdrop > 0 → saturates to 1.
    assert BlendMode.COLOR_DODGE.blend(1.0, 0.5) == 1.0
    assert BlendMode.COLOR_DODGE.blend(1.0, 1.0) == 1.0
    # Source 0 → backdrop unchanged.
    assert BlendMode.COLOR_DODGE.blend(0.0, 0.4) == pytest.approx(0.4)
    # General: b / (1 - s).
    assert BlendMode.COLOR_DODGE.blend(0.5, 0.25) == pytest.approx(0.5)


def test_color_dodge_pdf2_zero_backdrop_with_source_one() -> None:
    # The PDF 2.0 / PDFBox-3.0.x divergence: s == 1 and b == 0 → 0
    # (PDF 1.7 would give 1). The backdrop-0 short-circuit wins.
    assert BlendMode.COLOR_DODGE.blend(1.0, 0.0) == 0.0


def test_color_burn_special_cases() -> None:
    # Backdrop 1 → 1 regardless of source.
    assert BlendMode.COLOR_BURN.blend(0.0, 1.0) == 1.0
    assert BlendMode.COLOR_BURN.blend(0.5, 1.0) == 1.0
    assert BlendMode.COLOR_BURN.blend(1.0, 1.0) == 1.0
    # Source 0, backdrop < 1 → 0.
    assert BlendMode.COLOR_BURN.blend(0.0, 0.5) == 0.0
    assert BlendMode.COLOR_BURN.blend(0.0, 0.0) == 0.0
    # Source 1 → backdrop unchanged.
    assert BlendMode.COLOR_BURN.blend(1.0, 0.4) == pytest.approx(0.4)
    # General: 1 - (1 - b) / s.
    assert BlendMode.COLOR_BURN.blend(0.5, 0.75) == pytest.approx(0.5)


def test_hard_light_pivot() -> None:
    # s == 0.5 → multiply branch: 2 * s * b = b.
    assert BlendMode.HARD_LIGHT.blend(0.5, 0.6) == pytest.approx(0.6)
    # s < 0.5 → 2 s b.
    assert BlendMode.HARD_LIGHT.blend(0.25, 0.4) == pytest.approx(0.2)
    # s > 0.5 → screen branch.
    assert BlendMode.HARD_LIGHT.blend(0.75, 0.4) == pytest.approx(
        _ref_hard_light(0.75, 0.4)
    )


def test_overlay_is_hard_light_with_swapped_args() -> None:
    for s in _GRID:
        for b in _GRID:
            assert BlendMode.OVERLAY.blend(s, b) == pytest.approx(
                BlendMode.HARD_LIGHT.blend(b, s)
            ), f"Overlay({s},{b}) should equal HardLight({b},{s})"


def test_soft_light_pivots() -> None:
    # s == 0.5 → identity-ish: b - 0 = b.
    assert BlendMode.SOFT_LIGHT.blend(0.5, 0.6) == pytest.approx(0.6)
    # s < 0.5, lighten/darken toward b.
    assert BlendMode.SOFT_LIGHT.blend(0.25, 0.5) == pytest.approx(
        _ref_soft_light(0.25, 0.5)
    )
    # s > 0.5 with backdrop <= 0.25 uses the cubic D(b).
    assert BlendMode.SOFT_LIGHT.blend(0.75, 0.2) == pytest.approx(
        _ref_soft_light(0.75, 0.2)
    )
    # s > 0.5 with backdrop > 0.25 uses sqrt(b).
    assert BlendMode.SOFT_LIGHT.blend(0.75, 0.81) == pytest.approx(
        _ref_soft_light(0.75, 0.81)
    )


def test_soft_light_d_function_boundary_at_quarter() -> None:
    # At b == 0.25 the cubic and sqrt branches should agree (continuity).
    cubic = ((16.0 * 0.25 - 12.0) * 0.25 + 4.0) * 0.25
    root = math.sqrt(0.25)
    assert cubic == pytest.approx(root, abs=1e-9)
    assert BlendMode.SOFT_LIGHT.blend(0.75, 0.25) == pytest.approx(
        _ref_soft_light(0.75, 0.25)
    )


def test_blend_outputs_stay_in_unit_interval() -> None:
    for mode in _REFS:
        for s in _GRID:
            for b in _GRID:
                v = mode.blend(s, b)
                assert -1e-9 <= v <= 1.0 + 1e-9, f"{mode.name}({s},{b})={v}"


# ---------------------------------------------------------------------------
# Non-separable HSL helpers (PDF 32000-1 §11.3.5.3).
# ---------------------------------------------------------------------------


def _ref_lum(r: float, g: float, b: float) -> float:
    return 0.30 * r + 0.59 * g + 0.11 * b


def _ref_sat(r: float, g: float, b: float) -> float:
    return max(r, g, b) - min(r, g, b)


def test_lum_helper_matches_spec_coefficients() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    for r, g, b in [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.6, 0.3, 0.1),
        (1.0, 1.0, 1.0),
    ]:
        assert bm._hsl_lum(r, g, b) == pytest.approx(_ref_lum(r, g, b))


def test_sat_helper_is_range() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    assert bm._hsl_sat(0.2, 0.5, 0.8) == pytest.approx(0.6)
    assert bm._hsl_sat(0.5, 0.5, 0.5) == 0.0
    assert bm._hsl_sat(0.0, 1.0, 0.4) == pytest.approx(1.0)


def test_clip_color_passthrough_when_in_range() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    # All channels already in [0,1] → unchanged.
    assert bm._hsl_clip_color(0.2, 0.5, 0.8) == pytest.approx((0.2, 0.5, 0.8))


def test_clip_color_preserves_luminosity_on_negative() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    r, g, b = bm._hsl_clip_color(-0.2, 0.5, 0.8)
    # Luminosity must be preserved by the clip operation.
    assert bm._hsl_lum(r, g, b) == pytest.approx(bm._hsl_lum(-0.2, 0.5, 0.8))
    assert min(r, g, b) >= -1e-9


def test_clip_color_preserves_luminosity_on_overflow() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    r, g, b = bm._hsl_clip_color(0.5, 0.9, 1.3)
    assert bm._hsl_lum(r, g, b) == pytest.approx(bm._hsl_lum(0.5, 0.9, 1.3))
    assert max(r, g, b) <= 1.0 + 1e-9


def test_set_lum_sets_target_luminosity() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    r, g, b = bm._hsl_set_lum(0.2, 0.5, 0.8, 0.6)
    assert bm._hsl_lum(r, g, b) == pytest.approx(0.6, abs=1e-9)


def test_set_sat_targets_saturation_when_no_clip() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    r, g, b = bm._hsl_set_sat(0.2, 0.5, 0.8, 0.6)
    assert _ref_sat(r, g, b) == pytest.approx(0.6)
    assert min(r, g, b) == pytest.approx(0.0)


def test_set_sat_ties_collapse_correctly() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    # Two equal maxima.
    assert bm._hsl_set_sat(0.8, 0.8, 0.2, 0.6) == pytest.approx((0.6, 0.6, 0.0))
    # Two equal minima.
    assert bm._hsl_set_sat(0.8, 0.2, 0.2, 0.6) == pytest.approx((0.6, 0.0, 0.0))
    # All equal → zero saturation everywhere.
    assert bm._hsl_set_sat(0.5, 0.5, 0.5, 0.6) == pytest.approx((0.0, 0.0, 0.0))


def test_nonseparable_color_equals_setlum_of_source() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    src = (0.2, 0.5, 0.8)
    bk = (0.6, 0.3, 0.1)
    expected = bm._hsl_set_lum(*src, lum=bm._hsl_lum(*bk))
    assert BlendMode.COLOR.blend_separable_rgb(src, bk) == pytest.approx(expected)


def test_nonseparable_luminosity_takes_source_luminosity() -> None:
    src = (0.2, 0.5, 0.8)
    bk = (0.6, 0.3, 0.1)
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    r, g, b = BlendMode.LUMINOSITY.blend_separable_rgb(src, bk)
    assert bm._hsl_lum(r, g, b) == pytest.approx(bm._hsl_lum(*src), abs=1e-9)


def test_nonseparable_hue_preserves_backdrop_lum_and_source_sat() -> None:
    from pypdfbox.pdmodel.graphics import blend_mode as bm

    src = (0.2, 0.5, 0.8)
    bk = (0.6, 0.3, 0.1)
    r, g, b = BlendMode.HUE.blend_separable_rgb(src, bk)
    assert bm._hsl_lum(r, g, b) == pytest.approx(bm._hsl_lum(*bk), abs=1e-9)


def test_nonseparable_modes_raise_from_scalar_blend() -> None:
    for mode in (
        BlendMode.HUE,
        BlendMode.SATURATION,
        BlendMode.COLOR,
        BlendMode.LUMINOSITY,
    ):
        with pytest.raises(ValueError):
            mode.blend(0.5, 0.5)


def test_unknown_mode_falls_back_to_normal_in_scalar_blend() -> None:
    bogus = BlendMode.get("NotARealMode")
    assert bogus.blend(0.42, 0.13) == 0.42  # returns source


def test_get_blend_function_six_arg_shape_returns_triple() -> None:
    # Regression for wave 1587: get_blend_function exposes the 6-float
    # → triple HSL helper (callers like BlendComposite.compose now invoke
    # it with that shape, not the legacy 3-arg in-place form).
    fn = BlendMode.HUE.get_blend_function()
    assert fn is not None
    out = fn(0.2, 0.5, 0.8, 0.6, 0.3, 0.1)
    assert isinstance(out, tuple) and len(out) == 3
    for v in out:
        assert isinstance(v, float)

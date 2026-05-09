from __future__ import annotations

import pytest

import pypdfbox.pdmodel.graphics.blend_mode as blend_module
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.blend_mode import (
    BlendMode,
    _hsl_clip_color,
)


def test_wave677_non_separable_rgb_clips_high_luminosity_result() -> None:
    out = BlendMode.COLOR.blend_separable_rgb(
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 1.0),
    )

    assert out == pytest.approx((1.0, 1.0, 1.0))


def test_wave677_saturation_with_gray_backdrop_uses_zero_saturation() -> None:
    out = BlendMode.SATURATION.blend_separable_rgb(
        (0.8, 0.2, 0.1),
        (0.4, 0.4, 0.4),
    )

    assert out == pytest.approx((0.4, 0.4, 0.4))


def test_wave677_clip_color_handles_degenerate_low_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(blend_module, "_hsl_lum", lambda r, g, b: min(r, g, b))

    assert _hsl_clip_color(-0.25, -0.25, -0.25) == pytest.approx(
        (-0.25, -0.25, -0.25)
    )


def test_wave677_clip_color_handles_degenerate_high_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(blend_module, "_hsl_lum", lambda r, g, b: max(r, g, b))

    assert _hsl_clip_color(1.25, 1.25, 1.25) == pytest.approx(
        (1.25, 1.25, 1.25)
    )


def test_wave677_get_instance_array_compatible_resolves_to_normal() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("NotAStandardMode"))
    arr.add(COSName.get_pdf_name("Compatible"))
    arr.add(COSName.get_pdf_name("Multiply"))

    assert BlendMode.get_instance(arr) is BlendMode.NORMAL


def test_wave677_from_cos_array_with_no_name_entries_returns_none() -> None:
    arr = COSArray()
    arr.add(COSDictionary())

    assert BlendMode.from_cos(arr) is None


def test_wave677_equality_with_unrelated_type_is_false() -> None:
    assert (BlendMode.NORMAL == "Normal") is False

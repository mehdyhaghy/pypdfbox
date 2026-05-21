"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/blend/BlendModeTest.java

Upstream baseline: PDFBox 3.0.x. The companion file ``test_blend_mode.py`` in
this directory covers ``get_instance`` dispatch + the HSL/saturation/luminosity
helpers; this file ports the per-mode channel-function assertions
(``getBlendFunction`` / ``getBlendChannelFunction`` / ``getCOSName``) that
remained out of the original port.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

# ---------------------------------------------------------------------------
# testInstances — dispatch via getInstance(...). Mirrors lines 41-69.
# ---------------------------------------------------------------------------


def test_instances() -> None:
    assert BlendMode.get_instance(COSName.get_pdf_name("Normal")) is BlendMode.NORMAL
    assert BlendMode.get_instance(COSName.get_pdf_name("Compatible")) is BlendMode.NORMAL
    assert BlendMode.get_instance(COSName.get_pdf_name("Multiply")) is BlendMode.MULTIPLY
    assert BlendMode.get_instance(COSName.get_pdf_name("Screen")) is BlendMode.SCREEN
    assert BlendMode.get_instance(COSName.get_pdf_name("Overlay")) is BlendMode.OVERLAY
    assert BlendMode.get_instance(COSName.get_pdf_name("Darken")) is BlendMode.DARKEN
    assert BlendMode.get_instance(COSName.get_pdf_name("Lighten")) is BlendMode.LIGHTEN
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("ColorDodge"))
        is BlendMode.COLOR_DODGE
    )
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("ColorBurn"))
        is BlendMode.COLOR_BURN
    )
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("HardLight"))
        is BlendMode.HARD_LIGHT
    )
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("SoftLight"))
        is BlendMode.SOFT_LIGHT
    )
    assert BlendMode.get_instance(COSName.get_pdf_name("Difference")) is BlendMode.DIFFERENCE
    assert BlendMode.get_instance(COSName.get_pdf_name("Exclusion")) is BlendMode.EXCLUSION
    assert BlendMode.get_instance(COSName.get_pdf_name("Hue")) is BlendMode.HUE
    assert BlendMode.get_instance(COSName.get_pdf_name("Saturation")) is BlendMode.SATURATION
    assert BlendMode.get_instance(COSName.get_pdf_name("Luminosity")) is BlendMode.LUMINOSITY
    assert BlendMode.get_instance(COSName.get_pdf_name("Color")) is BlendMode.COLOR

    overlay_array = COSArray()
    overlay_array.add(COSName.get_pdf_name("Overlay"))
    assert BlendMode.get_instance(overlay_array) is BlendMode.OVERLAY

    int_array = COSArray()
    int_array.add(COSInteger.get(0))
    # Upstream: ``BlendMode.getInstance(cosArrayInteger)`` falls back to NORMAL
    # because the first array entry is not a ``COSName``.
    assert BlendMode.get_instance(int_array) is BlendMode.NORMAL


# ---------------------------------------------------------------------------
# Per-mode channel-function assertions. For separable modes, the upstream
# checks that ``getBlendFunction()`` is ``null`` and
# ``getBlendChannelFunction()`` is non-null; the Python port returns
# ``None`` for the non-existent direction.
# ---------------------------------------------------------------------------


def _channel(mode: BlendMode, src: float, dest: float) -> float:
    """Apply the separable per-channel blend. Mirrors upstream's
    ``mode.getBlendChannelFunction().blendChannel(src, dest)``."""
    fn = mode.get_blend_channel_function()
    assert fn is not None, f"{mode.get_name()} should be separable"
    return fn(src, dest)


def test_blend_mode_normal() -> None:
    assert BlendMode.NORMAL.is_separable_blend_mode() is True
    assert BlendMode.NORMAL.get_blend_function() is None
    assert BlendMode.NORMAL.get_blend_channel_function() is not None
    assert BlendMode.NORMAL.get_cos_name() == COSName.get_pdf_name("Normal")
    # Java: assertEquals(3f, ...blendChannel(3f, 5f));
    assert _channel(BlendMode.NORMAL, 3.0, 5.0) == 3.0
    # COMPATIBLE is a synonym whose CosName resolves back to NORMAL.
    assert BlendMode.COMPATIBLE.get_cos_name() == COSName.get_pdf_name("Normal")


def test_blend_mode_multiply() -> None:
    assert BlendMode.MULTIPLY.is_separable_blend_mode() is True
    assert BlendMode.MULTIPLY.get_blend_function() is None
    assert BlendMode.MULTIPLY.get_blend_channel_function() is not None
    assert BlendMode.MULTIPLY.get_cos_name() == COSName.get_pdf_name("Multiply")
    assert _channel(BlendMode.MULTIPLY, 3.0, 5.0) == 15.0


def test_blend_mode_screen() -> None:
    assert BlendMode.SCREEN.is_separable_blend_mode() is True
    assert BlendMode.SCREEN.get_blend_function() is None
    assert BlendMode.SCREEN.get_blend_channel_function() is not None
    assert BlendMode.SCREEN.get_cos_name() == COSName.get_pdf_name("Screen")
    # Java: assertEquals(-7f, screen.blendChannel(3f, 5f));  // 3+5-3*5 = -7
    assert _channel(BlendMode.SCREEN, 3.0, 5.0) == -7.0


def test_blend_mode_overlay() -> None:
    assert BlendMode.OVERLAY.is_separable_blend_mode() is True
    assert BlendMode.OVERLAY.get_blend_function() is None
    assert BlendMode.OVERLAY.get_blend_channel_function() is not None
    assert BlendMode.OVERLAY.get_cos_name() == COSName.get_pdf_name("Overlay")
    assert _channel(BlendMode.OVERLAY, 1.0, 0.0) == 0.0
    assert _channel(BlendMode.OVERLAY, 0.5, 0.3) == pytest.approx(0.3)


def test_blend_mode_darken() -> None:
    assert BlendMode.DARKEN.is_separable_blend_mode() is True
    assert BlendMode.DARKEN.get_blend_function() is None
    assert BlendMode.DARKEN.get_blend_channel_function() is not None
    assert BlendMode.DARKEN.get_cos_name() == COSName.get_pdf_name("Darken")
    assert _channel(BlendMode.DARKEN, 3.0, 5.0) == 3.0


def test_blend_mode_lighten() -> None:
    assert BlendMode.LIGHTEN.is_separable_blend_mode() is True
    assert BlendMode.LIGHTEN.get_blend_function() is None
    assert BlendMode.LIGHTEN.get_blend_channel_function() is not None
    assert BlendMode.LIGHTEN.get_cos_name() == COSName.get_pdf_name("Lighten")
    assert _channel(BlendMode.LIGHTEN, 3.0, 5.0) == 5.0


def test_blend_mode_color_dodge() -> None:
    assert BlendMode.COLOR_DODGE.is_separable_blend_mode() is True
    assert BlendMode.COLOR_DODGE.get_blend_function() is None
    assert BlendMode.COLOR_DODGE.get_blend_channel_function() is not None
    assert BlendMode.COLOR_DODGE.get_cos_name() == COSName.get_pdf_name("ColorDodge")
    # blendChannel(1, 0) = 0 (b=0, b/(1-s) clamps to 0).
    assert _channel(BlendMode.COLOR_DODGE, 1.0, 0.0) == 0.0
    # blendChannel(0.3, 0.7) -> min(1, 0.7/0.7) = 1.
    assert _channel(BlendMode.COLOR_DODGE, 0.3, 0.7) == pytest.approx(1.0)


def test_blend_mode_color_burn() -> None:
    assert BlendMode.COLOR_BURN.is_separable_blend_mode() is True
    assert BlendMode.COLOR_BURN.get_blend_function() is None
    assert BlendMode.COLOR_BURN.get_blend_channel_function() is not None
    assert BlendMode.COLOR_BURN.get_cos_name() == COSName.get_pdf_name("ColorBurn")
    # blendChannel(0, 1) = 1 - min(1, 0/0) -> spec says result is 1 when s == 0.
    assert _channel(BlendMode.COLOR_BURN, 0.0, 1.0) == 1.0
    # blendChannel(0.7, 0.3) = 1 - min(1, 0.7/0.7) = 0.
    assert _channel(BlendMode.COLOR_BURN, 0.7, 0.3) == pytest.approx(0.0)


def test_blend_mode_hard_light() -> None:
    assert BlendMode.HARD_LIGHT.is_separable_blend_mode() is True
    assert BlendMode.HARD_LIGHT.get_blend_function() is None
    assert BlendMode.HARD_LIGHT.get_blend_channel_function() is not None
    assert BlendMode.HARD_LIGHT.get_cos_name() == COSName.get_pdf_name("HardLight")
    assert _channel(BlendMode.HARD_LIGHT, 0.0, 0.5) == 0.0
    assert _channel(BlendMode.HARD_LIGHT, 0.2, 0.5) == pytest.approx(0.2)
    assert _channel(BlendMode.HARD_LIGHT, 0.6, 0.4) == pytest.approx(0.52)


def test_blend_mode_soft_light() -> None:
    assert BlendMode.SOFT_LIGHT.is_separable_blend_mode() is True
    assert BlendMode.SOFT_LIGHT.get_blend_function() is None
    assert BlendMode.SOFT_LIGHT.get_blend_channel_function() is not None
    assert BlendMode.SOFT_LIGHT.get_cos_name() == COSName.get_pdf_name("SoftLight")
    assert _channel(BlendMode.SOFT_LIGHT, 0.0, 0.5) == pytest.approx(0.25)
    assert _channel(BlendMode.SOFT_LIGHT, 0.2, 0.5) == pytest.approx(0.35)
    assert _channel(BlendMode.SOFT_LIGHT, 0.5, 0.2) == pytest.approx(0.2)


def test_blend_mode_difference() -> None:
    assert BlendMode.DIFFERENCE.is_separable_blend_mode() is True
    assert BlendMode.DIFFERENCE.get_blend_function() is None
    assert BlendMode.DIFFERENCE.get_blend_channel_function() is not None
    assert BlendMode.DIFFERENCE.get_cos_name() == COSName.get_pdf_name("Difference")
    assert _channel(BlendMode.DIFFERENCE, 3.0, 5.0) == 2.0


def test_blend_mode_exclusion() -> None:
    assert BlendMode.EXCLUSION.is_separable_blend_mode() is True
    assert BlendMode.EXCLUSION.get_blend_function() is None
    assert BlendMode.EXCLUSION.get_blend_channel_function() is not None
    assert BlendMode.EXCLUSION.get_cos_name() == COSName.get_pdf_name("Exclusion")


def test_blend_mode_hue() -> None:
    assert BlendMode.HUE.is_separable_blend_mode() is False
    assert BlendMode.HUE.get_blend_function() is not None
    assert BlendMode.HUE.get_blend_channel_function() is None
    assert BlendMode.HUE.get_cos_name() == COSName.get_pdf_name("Hue")


def test_blend_mode_saturation() -> None:
    assert BlendMode.SATURATION.is_separable_blend_mode() is False
    assert BlendMode.SATURATION.get_blend_function() is not None
    assert BlendMode.SATURATION.get_blend_channel_function() is None
    assert BlendMode.SATURATION.get_cos_name() == COSName.get_pdf_name("Saturation")


def test_blend_mode_luminosity() -> None:
    assert BlendMode.LUMINOSITY.is_separable_blend_mode() is False
    assert BlendMode.LUMINOSITY.get_blend_function() is not None
    assert BlendMode.LUMINOSITY.get_blend_channel_function() is None
    assert BlendMode.LUMINOSITY.get_cos_name() == COSName.get_pdf_name("Luminosity")


def test_blend_mode_color() -> None:
    assert BlendMode.COLOR.is_separable_blend_mode() is False
    assert BlendMode.COLOR.get_blend_function() is not None
    assert BlendMode.COLOR.get_blend_channel_function() is None
    assert BlendMode.COLOR.get_cos_name() == COSName.get_pdf_name("Color")

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDShadingPattern,
    PDTilingPattern,
)
from pypdfbox.pdmodel.pd_resources import PDResources

_PATTERN = COSName.get_pdf_name("Pattern")
_PATTERN_TYPE = COSName.get_pdf_name("PatternType")


# ---------- get_initial_color ----------


def test_initial_color_is_empty_pattern() -> None:
    """Upstream ``PDPattern.getInitialColor()`` returns ``EMPTY_PATTERN``
    — a PDColor with empty components that paints nothing."""
    cs = PDPattern()
    initial = cs.get_initial_color()
    assert isinstance(initial, PDColor)
    assert initial.get_components() == []


def test_initial_color_is_empty_for_uncolored_pattern() -> None:
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    initial = cs.get_initial_color()
    assert initial.get_components() == []


def test_initial_color_color_space_round_trips_to_pattern() -> None:
    """Empty-pattern initial color still reports Pattern as its CS so
    ``PDColor.is_pattern()`` and renderers branch correctly."""
    cs = PDPattern()
    initial = cs.get_initial_color()
    assert initial.get_color_space() is cs
    assert initial.is_pattern()


# ---------- to_rgb (component-form) ----------


def test_to_rgb_uncolored_forwards_to_underlying_device_rgb() -> None:
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    rgb = cs.to_rgb([0.25, 0.5, 0.75])
    assert rgb is not None
    assert rgb == pytest.approx((0.25, 0.5, 0.75), abs=1e-6)


def test_to_rgb_uncolored_forwards_to_underlying_device_gray() -> None:
    cs = PDPattern(PDDeviceGray.INSTANCE)
    rgb = cs.to_rgb([0.4])
    assert rgb is not None
    assert rgb == pytest.approx((0.4, 0.4, 0.4), abs=1e-6)


def test_to_rgb_colored_returns_none_without_underlying() -> None:
    """Colored tiling patterns / shading patterns have no underlying CS
    — ``to_rgb`` returns ``None`` so callers can escalate to the
    renderer (upstream throws UnsupportedOperationException)."""
    cs = PDPattern()
    assert cs.to_rgb([]) is None


# ---------- get_pattern (resource resolution) ----------


def _resources_with_pattern(name: str, pattern_dict: COSDictionary) -> PDResources:
    """Build a ``PDResources`` whose ``/Pattern`` sub-dictionary
    contains exactly one pattern under ``name``."""
    resources = PDResources()
    pattern_subdict = COSDictionary()
    pattern_subdict.set_item(COSName.get_pdf_name(name), pattern_dict)
    resources.get_cos_object().set_item(_PATTERN, pattern_subdict)
    return resources


def test_get_pattern_resolves_tiling_pattern_by_name() -> None:
    tiling_stream = COSStream()
    tiling_stream.set_int(_PATTERN_TYPE, PDAbstractPattern.TYPE_TILING_PATTERN)
    resources = _resources_with_pattern("P1", tiling_stream)

    cs = PDPattern(resources=resources)
    color = PDColor([], cs, COSName.get_pdf_name("P1"))

    pattern = cs.get_pattern(color)
    assert isinstance(pattern, PDTilingPattern)
    assert pattern.get_pattern_type() == 1
    assert pattern.get_cos_object() is tiling_stream


def test_get_pattern_resolves_shading_pattern_by_name() -> None:
    shading_dict = COSDictionary()
    shading_dict.set_int(_PATTERN_TYPE, PDAbstractPattern.TYPE_SHADING_PATTERN)
    resources = _resources_with_pattern("Sh1", shading_dict)

    cs = PDPattern(resources=resources)
    color = PDColor([], cs, COSName.get_pdf_name("Sh1"))

    pattern = cs.get_pattern(color)
    assert isinstance(pattern, PDShadingPattern)
    assert pattern.get_pattern_type() == 2


def test_get_pattern_raises_when_no_resources_attached() -> None:
    cs = PDPattern()
    color = PDColor([], cs, COSName.get_pdf_name("P1"))
    with pytest.raises(OSError):
        cs.get_pattern(color)


def test_get_pattern_raises_when_color_has_no_pattern_name() -> None:
    resources = PDResources()
    cs = PDPattern(resources=resources)
    color = PDColor([], cs)  # pattern name omitted
    with pytest.raises(OSError):
        cs.get_pattern(color)


def test_get_pattern_raises_when_named_pattern_missing() -> None:
    """Name present but absent from /Resources/Pattern — mirrors
    upstream ``IOException("pattern X was not found")`` (we use OSError
    per the project's Java→Python exception mapping)."""
    resources = PDResources()  # no /Pattern entry at all
    cs = PDPattern(resources=resources)
    color = PDColor([], cs, COSName.get_pdf_name("Missing"))
    with pytest.raises(OSError, match="not found"):
        cs.get_pattern(color)


def test_get_pattern_works_for_uncolored_tiling_pattern_form() -> None:
    """Uncolored tiling: PDPattern carries an underlying color space *and*
    resolves named patterns. The two surfaces are orthogonal — exercise
    them together."""
    tiling_stream = COSStream()
    tiling_stream.set_int(_PATTERN_TYPE, PDAbstractPattern.TYPE_TILING_PATTERN)
    tiling_stream.set_int(COSName.get_pdf_name("PaintType"), 2)
    resources = _resources_with_pattern("UP1", tiling_stream)

    cs = PDPattern(PDDeviceRGB.INSTANCE, resources=resources)
    color = PDColor([0.1, 0.2, 0.3], cs, COSName.get_pdf_name("UP1"))

    # Pattern resolution returns the named tiling pattern.
    pattern = cs.get_pattern(color)
    assert isinstance(pattern, PDTilingPattern)
    assert pattern.get_paint_type() == 2

    # Tint resolution forwards to the underlying color space.
    rgb = cs.to_rgb([0.1, 0.2, 0.3])
    assert rgb == pytest.approx((0.1, 0.2, 0.3), abs=1e-6)


# ---------- set_resources ----------


def test_set_resources_attaches_after_construction() -> None:
    cs = PDPattern()
    assert cs.get_resources() is None

    tiling_stream = COSStream()
    tiling_stream.set_int(_PATTERN_TYPE, 1)
    resources = _resources_with_pattern("P1", tiling_stream)

    cs.set_resources(resources)
    assert cs.get_resources() is resources

    color = PDColor([], cs, COSName.get_pdf_name("P1"))
    pattern = cs.get_pattern(color)
    assert isinstance(pattern, PDTilingPattern)


def test_set_resources_none_clears() -> None:
    cs = PDPattern(resources=PDResources())
    cs.set_resources(None)
    assert cs.get_resources() is None

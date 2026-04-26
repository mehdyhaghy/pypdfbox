from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDShadingPattern,
    PDTilingPattern,
)
from pypdfbox.pdmodel.pd_resources import PDResources

_PATTERN_TYPE = COSName.get_pdf_name("PatternType")
_SHADING = COSName.get_pdf_name("Shading")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]


# ---------- PDTilingPattern ----------


def test_tiling_pattern_type_is_one() -> None:
    pattern = PDTilingPattern()
    assert pattern.get_pattern_type() == PDAbstractPattern.TYPE_TILING_PATTERN
    assert pattern.get_pattern_type() == 1
    # Fresh stream gets /Type /Pattern and /PatternType 1 written.
    assert pattern.get_cos_object().get_name(_TYPE) == "Pattern"
    assert pattern.get_cos_object().get_int(_PATTERN_TYPE, 0) == 1


def test_tiling_paint_type_round_trip() -> None:
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_UNCOLORED)
    assert pattern.get_paint_type() == 2

    pattern.set_paint_type(PDTilingPattern.PAINT_COLORED)
    assert pattern.get_paint_type() == 1


def test_tiling_x_step_y_step_round_trip() -> None:
    pattern = PDTilingPattern()
    pattern.set_x_step(72.5)
    pattern.set_y_step(36.25)
    assert pattern.get_x_step() == pytest.approx(72.5)
    assert pattern.get_y_step() == pytest.approx(36.25)


def test_tiling_resources_round_trip() -> None:
    pattern = PDTilingPattern()
    # Fresh ctor attaches an empty PDResources by default.
    initial = pattern.get_resources()
    assert initial is not None
    assert isinstance(initial, PDResources)

    fresh = PDResources()
    pattern.set_resources(fresh)
    out = pattern.get_resources()
    assert out is not None
    assert out.get_cos_object() is fresh.get_cos_object()


# ---------- PDShadingPattern ----------


def test_shading_pattern_type_is_two() -> None:
    pattern = PDShadingPattern()
    assert pattern.get_pattern_type() == PDAbstractPattern.TYPE_SHADING_PATTERN
    assert pattern.get_pattern_type() == 2
    assert pattern.get_cos_object().get_int(_PATTERN_TYPE, 0) == 2


def test_shading_set_shading_round_trip() -> None:
    pattern = PDShadingPattern()
    assert pattern.get_shading() is None

    raw_shading = COSDictionary()
    raw_shading.set_int("ShadingType", 2)
    pattern.set_shading(raw_shading)

    out = pattern.get_shading()
    assert out is raw_shading
    assert pattern.get_cos_object().get_dictionary_object(_SHADING) is raw_shading

    pattern.set_shading(None)
    assert pattern.get_shading() is None


# ---------- PDAbstractPattern.create dispatch ----------


def test_create_dispatches_to_tiling_for_pattern_type_one() -> None:
    stream = COSStream()
    stream.set_int(_PATTERN_TYPE, 1)

    result = PDAbstractPattern.create(stream)
    assert isinstance(result, PDTilingPattern)
    assert result.get_pattern_type() == 1
    assert result.get_cos_object() is stream


def test_create_dispatches_to_shading_for_pattern_type_two() -> None:
    dictionary = COSDictionary()
    dictionary.set_int(_PATTERN_TYPE, 2)

    result = PDAbstractPattern.create(dictionary)
    assert isinstance(result, PDShadingPattern)
    assert result.get_pattern_type() == 2
    assert result.get_cos_object() is dictionary


def test_create_returns_none_for_none() -> None:
    assert PDAbstractPattern.create(None) is None


def test_create_raises_for_unknown_pattern_type() -> None:
    dictionary = COSDictionary()
    dictionary.set_int(_PATTERN_TYPE, 99)
    with pytest.raises(OSError):
        PDAbstractPattern.create(dictionary)

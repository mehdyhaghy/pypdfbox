from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDShadingPattern,
    PDTilingPattern,
)
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_BBOX = COSName.get_pdf_name("BBox")
_EXT_G_STATE = COSName.get_pdf_name("ExtGState")
_MATRIX = COSName.get_pdf_name("Matrix")
_PAINT_TYPE = COSName.get_pdf_name("PaintType")
_SHADING = COSName.get_pdf_name("Shading")
_X_STEP = COSName.get_pdf_name("XStep")
_Y_STEP = COSName.get_pdf_name("YStep")


# ---------- PDAbstractPattern ----------


def test_abstract_pattern_get_matrix_default_identity() -> None:
    """No ``/Matrix`` entry → identity matrix per PDF §8.7."""
    pattern = PDTilingPattern()
    assert pattern.get_cos_object().get_dictionary_object(_MATRIX) is None
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_abstract_pattern_set_matrix_round_trip() -> None:
    pattern = PDTilingPattern()
    pattern.set_matrix([2.0, 0.0, 0.0, 3.0, 10.0, 20.0])
    assert pattern.get_matrix() == [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]
    arr = pattern.get_cos_object().get_dictionary_object(_MATRIX)
    assert isinstance(arr, COSArray)
    assert arr.size() == 6


def test_abstract_pattern_set_matrix_clear_with_none() -> None:
    pattern = PDTilingPattern()
    pattern.set_matrix([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    pattern.set_matrix(None)
    assert pattern.get_cos_object().get_dictionary_object(_MATRIX) is None
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_abstract_pattern_set_matrix_rejects_wrong_length() -> None:
    pattern = PDTilingPattern()
    with pytest.raises(ValueError):
        pattern.set_matrix([1.0, 2.0, 3.0])


def test_abstract_pattern_get_ext_g_state_returns_typed_wrapper() -> None:
    pattern = PDShadingPattern()
    assert pattern.get_ext_g_state() is None

    extgs = PDExtendedGraphicsState()
    pattern.set_ext_g_state(extgs)
    out = pattern.get_ext_g_state()
    assert out is not None
    assert isinstance(out, PDExtendedGraphicsState)
    assert out.get_cos_object() is extgs.get_cos_object()
    assert (
        pattern.get_cos_object().get_dictionary_object(_EXT_G_STATE)
        is extgs.get_cos_object()
    )


def test_abstract_pattern_set_ext_g_state_accepts_raw_dict() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    pattern.set_ext_g_state(raw)
    out = pattern.get_ext_g_state()
    assert out is not None
    assert out.get_cos_object() is raw


def test_abstract_pattern_set_ext_g_state_none_clears() -> None:
    pattern = PDShadingPattern()
    pattern.set_ext_g_state(PDExtendedGraphicsState())
    pattern.set_ext_g_state(None)
    assert pattern.get_ext_g_state() is None
    assert pattern.get_cos_object().get_dictionary_object(_EXT_G_STATE) is None


def test_abstract_pattern_set_ext_g_state_rejects_garbage() -> None:
    pattern = PDShadingPattern()
    with pytest.raises(TypeError):
        pattern.set_ext_g_state("not a dict")  # type: ignore[arg-type]


def test_abstract_pattern_type_predicates() -> None:
    tiling = PDTilingPattern()
    shading = PDShadingPattern()

    assert tiling.is_tiling_pattern() is True
    assert tiling.is_shading_pattern() is False

    assert shading.is_tiling_pattern() is False
    assert shading.is_shading_pattern() is True


# ---------- PDTilingPattern ----------


def test_tiling_paint_type_constants_match_spec() -> None:
    assert PDTilingPattern.PAINT_TYPE_COLORED == 1
    assert PDTilingPattern.PAINT_TYPE_UNCOLORED == 2


def test_tiling_tiling_type_constants_match_spec() -> None:
    assert PDTilingPattern.TILING_TYPE_CONSTANT_SPACING == 1
    assert PDTilingPattern.TILING_TYPE_NO_DISTORTION == 2
    assert (
        PDTilingPattern.TILING_TYPE_CONSTANT_SPACING_AND_FASTER_TILING == 3
    )


def test_tiling_paint_type_round_trip_typed_constants() -> None:
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
    assert pattern.get_paint_type() == 2
    assert pattern.get_cos_object().get_int(_PAINT_TYPE, 0) == 2

    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    assert pattern.get_paint_type() == 1
    assert pattern.get_cos_object().get_int(_PAINT_TYPE, 0) == 1


def test_tiling_x_step_y_step_round_trip_typed() -> None:
    pattern = PDTilingPattern()
    pattern.set_x_step(48.0)
    pattern.set_y_step(96.0)
    assert pattern.get_x_step() == pytest.approx(48.0)
    assert pattern.get_y_step() == pytest.approx(96.0)
    assert pattern.get_cos_object().get_float(_X_STEP) == pytest.approx(48.0)
    assert pattern.get_cos_object().get_float(_Y_STEP) == pytest.approx(96.0)


def test_tiling_b_box_round_trip_typed_pdrectangle() -> None:
    pattern = PDTilingPattern()
    assert pattern.get_b_box() is None

    rect = PDRectangle(0.0, 0.0, 100.0, 200.0)
    pattern.set_b_box(rect)

    out = pattern.get_b_box()
    assert out is not None
    assert isinstance(out, PDRectangle)
    assert out.get_lower_left_x() == pytest.approx(0.0)
    assert out.get_lower_left_y() == pytest.approx(0.0)
    assert out.get_upper_right_x() == pytest.approx(100.0)
    assert out.get_upper_right_y() == pytest.approx(200.0)
    assert out.get_width() == pytest.approx(100.0)
    assert out.get_height() == pytest.approx(200.0)

    raw = pattern.get_cos_object().get_dictionary_object(_BBOX)
    assert isinstance(raw, COSArray)
    assert raw.size() == 4


def test_tiling_b_box_accepts_raw_cos_array() -> None:
    pattern = PDTilingPattern()
    arr = COSArray(
        [COSFloat(1.0), COSFloat(2.0), COSFloat(11.0), COSFloat(22.0)]
    )
    pattern.set_b_box(arr)
    out = pattern.get_b_box()
    assert out is not None
    assert out.get_lower_left_x() == pytest.approx(1.0)
    assert out.get_upper_right_y() == pytest.approx(22.0)


def test_tiling_b_box_none_clears() -> None:
    pattern = PDTilingPattern()
    pattern.set_b_box(PDRectangle(0.0, 0.0, 5.0, 5.0))
    pattern.set_b_box(None)
    assert pattern.get_b_box() is None
    assert pattern.get_cos_object().get_dictionary_object(_BBOX) is None


def test_tiling_b_box_rejects_garbage() -> None:
    pattern = PDTilingPattern()
    with pytest.raises(TypeError):
        pattern.set_b_box(42)  # type: ignore[arg-type]


# ---------- PDShadingPattern ----------


def test_shading_get_shading_wraps_dict_into_pdshading() -> None:
    pattern = PDShadingPattern()
    assert pattern.get_shading() is None

    raw = COSDictionary()
    raw.set_int("ShadingType", PDShading.SHADING_TYPE2)
    pattern.set_shading(raw)

    out = pattern.get_shading()
    assert out is not None
    assert isinstance(out, PDShading)
    assert out.get_cos_object() is raw
    assert out.get_shading_type() == PDShading.SHADING_TYPE2


def test_shading_set_shading_accepts_typed_pdshading() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    raw.set_int("ShadingType", PDShading.SHADING_TYPE3)
    typed = PDShading.create(raw)
    assert typed is not None

    pattern.set_shading(typed)
    out = pattern.get_shading()
    assert out is not None
    assert out.get_cos_object() is raw
    assert (
        pattern.get_cos_object().get_dictionary_object(_SHADING) is raw
    )


def test_shading_set_shading_none_clears() -> None:
    pattern = PDShadingPattern()
    raw = COSDictionary()
    raw.set_int("ShadingType", PDShading.SHADING_TYPE1)
    pattern.set_shading(raw)
    pattern.set_shading(None)
    assert pattern.get_shading() is None
    assert pattern.get_cos_object().get_dictionary_object(_SHADING) is None


def test_shading_pattern_inherits_get_matrix_default_identity() -> None:
    pattern = PDShadingPattern()
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_shading_pattern_inherits_get_ext_g_state_typed() -> None:
    pattern = PDShadingPattern()
    extgs = PDExtendedGraphicsState()
    pattern.set_ext_g_state(extgs)
    out = pattern.get_ext_g_state()
    assert out is not None
    assert isinstance(out, PDExtendedGraphicsState)


# ---------- type-predicate cross-check via factory ----------


def test_factory_dispatch_preserves_type_predicates() -> None:
    from pypdfbox.cos import COSStream

    tiling_stream = COSStream()
    tiling_stream.set_int(COSName.get_pdf_name("PatternType"), 1)
    tiling = PDAbstractPattern.create(tiling_stream)
    assert tiling is not None
    assert tiling.is_tiling_pattern()
    assert not tiling.is_shading_pattern()

    shading_dict = COSDictionary()
    shading_dict.set_int(COSName.get_pdf_name("PatternType"), 2)
    shading = PDAbstractPattern.create(shading_dict)
    assert shading is not None
    assert shading.is_shading_pattern()
    assert not shading.is_tiling_pattern()

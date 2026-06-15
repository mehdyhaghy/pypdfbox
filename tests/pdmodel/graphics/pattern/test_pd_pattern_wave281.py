from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.pattern import PDShadingPattern, PDTilingPattern
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

_BBOX = COSName.get_pdf_name("BBox")
_EXT_G_STATE = COSName.get_pdf_name("ExtGState")
_MATRIX = COSName.get_pdf_name("Matrix")
_RESOURCES = COSName.RESOURCES  # type: ignore[attr-defined]
_SHADING = COSName.get_pdf_name("Shading")


def test_tiling_four_entry_malformed_b_box_coerces_and_has_true() -> None:
    # A 4-entry /BBox passes get_b_box's own length guard; upstream
    # ``new PDRectangle(COSArray)`` coerces the non-numeric slot to 0.0 and
    # normalizes, so ``[0, /NotANumber, 10, 20]`` yields a real rectangle and
    # has_b_box() is True.
    pattern = PDTilingPattern()
    malformed = COSArray(
        [
            COSFloat(0.0),
            COSName.get_pdf_name("NotANumber"),
            COSFloat(10.0),
            COSFloat(20.0),
        ]
    )
    pattern.get_cos_object().set_item(_BBOX, malformed)

    assert pattern.get_b_box() == PDRectangle(0.0, 0.0, 10.0, 20.0)
    assert pattern.has_b_box() is True


def test_pattern_matrix_has_and_clear_ignore_malformed_arrays() -> None:
    pattern = PDTilingPattern()
    pattern.set_matrix([1.0, 0.0, 0.0, 1.0, 3.0, 4.0])

    assert pattern.has_matrix() is True

    pattern.clear_matrix()
    assert pattern.has_matrix() is False
    assert pattern.get_cos_object().get_dictionary_object(_MATRIX) is None

    malformed = COSArray(
        [
            COSFloat(1.0),
            COSFloat(0.0),
            COSName.get_pdf_name("Bad"),
            COSFloat(1.0),
            COSFloat(3.0),
            COSFloat(4.0),
        ]
    )
    pattern.get_cos_object().set_item(_MATRIX, malformed)

    assert pattern.has_matrix() is False
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_ext_g_state_has_and_clear_helpers() -> None:
    pattern = PDTilingPattern()
    ext_g_state = PDExtendedGraphicsState()
    pattern.set_ext_g_state(ext_g_state)

    assert pattern.has_ext_g_state() is True
    assert pattern.has_extended_graphics_state() is True

    pattern.clear_ext_g_state()
    assert pattern.has_ext_g_state() is False
    assert pattern.get_cos_object().get_dictionary_object(_EXT_G_STATE) is None

    pattern.get_cos_object().set_item(_EXT_G_STATE, COSInteger.get(7))
    assert pattern.has_ext_g_state() is False
    assert pattern.get_ext_g_state() is None


def test_tiling_resources_has_clear_and_rejects_wrong_type() -> None:
    pattern = PDTilingPattern()
    assert pattern.has_resources() is True

    pattern.clear_resources()
    assert pattern.has_resources() is False
    assert pattern.get_resources() is None

    resources = PDResources()
    pattern.set_resources(resources)
    assert pattern.has_resources() is True
    assert pattern.get_cos_object().get_dictionary_object(
        _RESOURCES
    ) is resources.get_cos_object()

    with pytest.raises(TypeError):
        pattern.set_resources(COSInteger.get(1))  # type: ignore[arg-type]


def test_shading_has_and_clear_helpers_ignore_malformed_entries() -> None:
    pattern = PDShadingPattern()
    pattern.get_cos_object().set_item(_SHADING, COSInteger.get(2))

    assert pattern.has_shading() is False
    assert pattern.get_shading() is None

    raw_shading = COSDictionary()
    pattern.set_shading(raw_shading)
    assert pattern.has_shading() is True

    pattern.clear_shading()
    assert pattern.has_shading() is False
    assert pattern.get_cos_object().get_dictionary_object(_SHADING) is None


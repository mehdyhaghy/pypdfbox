from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.graphics.pattern import PDAbstractPattern, PDTilingPattern
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)

_EXT_G_STATE = COSName.get_pdf_name("ExtGState")
_MATRIX = COSName.get_pdf_name("Matrix")


def test_wave656_create_rejects_non_dictionary_input() -> None:
    with pytest.raises(TypeError, match="COSDictionary"):
        PDAbstractPattern.create(COSString("not a dict"))  # type: ignore[arg-type]


def test_wave656_base_pattern_type_must_be_overridden() -> None:
    with pytest.raises(NotImplementedError):
        PDAbstractPattern().get_pattern_type()


def test_wave656_set_matrix_accepts_raw_cos_array() -> None:
    pattern = PDTilingPattern()
    matrix = COSArray(
        [COSFloat(1), COSFloat(2), COSFloat(3), COSFloat(4), COSFloat(5), COSFloat(6)]
    )

    pattern.set_matrix(matrix)

    assert pattern.get_cos_object().get_dictionary_object(_MATRIX) is matrix
    assert pattern.get_matrix() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_wave656_set_matrix_rejects_adapter_returning_non_sequence() -> None:
    class BadTransform:
        def get_matrix(self) -> float:
            return 3.14

    with pytest.raises(TypeError, match="non-sequence"):
        PDTilingPattern().set_matrix(BadTransform())


def test_wave656_raw_extended_graphics_state_accessors_round_trip_and_clear() -> None:
    pattern = PDTilingPattern()
    raw = COSDictionary()

    assert pattern.get_extended_graphics_state() is None
    pattern.set_extended_graphics_state(raw)

    assert pattern.get_extended_graphics_state() is raw
    assert pattern.has_extended_graphics_state() is True
    pattern.set_extended_graphics_state(None)
    assert pattern.get_cos_object().get_dictionary_object(_EXT_G_STATE) is None


def test_wave656_typed_ext_g_state_setter_accepts_wrapper_raw_dict_and_none() -> None:
    pattern = PDTilingPattern()
    wrapper = PDExtendedGraphicsState()
    raw = COSDictionary()

    pattern.set_ext_g_state(wrapper)
    assert pattern.get_cos_object().get_dictionary_object(_EXT_G_STATE) is wrapper.get_cos_object()

    pattern.set_ext_g_state(raw)
    assert pattern.get_ext_g_state().get_cos_object() is raw  # type: ignore[union-attr]

    pattern.set_ext_g_state(None)
    assert pattern.get_ext_g_state() is None

from __future__ import annotations

import pytest

from pypdfbox.contentstream import OperatorName


def test_text_operator_constants() -> None:
    assert OperatorName.BEGIN_TEXT == "BT"
    assert OperatorName.END_TEXT == "ET"
    assert OperatorName.SHOW_TEXT == "Tj"
    assert OperatorName.SHOW_TEXT_ADJUSTED == "TJ"
    assert OperatorName.SET_FONT_AND_SIZE == "Tf"


def test_path_operator_constants() -> None:
    assert OperatorName.MOVE_TO == "m"
    assert OperatorName.LINE_TO == "l"
    assert OperatorName.CURVE_TO == "c"
    assert OperatorName.CLOSE_PATH == "h"
    assert OperatorName.APPEND_RECT == "re"


def test_painting_operator_constants() -> None:
    assert OperatorName.STROKE_PATH == "S"
    assert OperatorName.CLOSE_AND_STROKE == "s"
    assert OperatorName.FILL_NON_ZERO == "f"
    assert OperatorName.FILL_EVEN_ODD == "f*"
    assert OperatorName.LEGACY_FILL_NON_ZERO == "F"
    assert OperatorName.ENDPATH == "n"


def test_graphics_state_operator_constants() -> None:
    assert OperatorName.SAVE == "q"
    assert OperatorName.RESTORE == "Q"
    assert OperatorName.CONCAT == "cm"
    assert OperatorName.SET_LINE_WIDTH == "w"
    assert OperatorName.SET_GRAPHICS_STATE_PARAMS == "gs"


def test_color_operator_constants() -> None:
    assert OperatorName.STROKING_COLOR == "SC"
    assert OperatorName.NON_STROKING_COLOR == "sc"
    assert OperatorName.STROKING_COLOR_N == "SCN"
    assert OperatorName.NON_STROKING_COLOR_N == "scn"
    assert OperatorName.STROKING_COLOR_RGB == "RG"
    assert OperatorName.NON_STROKING_RGB == "rg"
    assert OperatorName.STROKING_COLOR_GRAY == "G"
    assert OperatorName.NON_STROKING_GRAY == "g"
    assert OperatorName.STROKING_COLOR_CMYK == "K"
    assert OperatorName.NON_STROKING_CMYK == "k"
    assert OperatorName.STROKING_COLORSPACE == "CS"
    assert OperatorName.NON_STROKING_COLORSPACE == "cs"


def test_inline_image_operator_constants() -> None:
    assert OperatorName.BEGIN_INLINE_IMAGE == "BI"
    assert OperatorName.BEGIN_INLINE_IMAGE_DATA == "ID"
    assert OperatorName.END_INLINE_IMAGE == "EI"


def test_marked_content_operator_constants() -> None:
    assert OperatorName.BEGIN_MARKED_CONTENT == "BMC"
    assert OperatorName.BEGIN_MARKED_CONTENT_SEQ == "BDC"
    assert OperatorName.END_MARKED_CONTENT == "EMC"
    assert OperatorName.MARKED_CONTENT_POINT == "MP"
    assert OperatorName.MARKED_CONTENT_POINT_WITH_PROPS == "DP"
    assert OperatorName.DRAW_OBJECT == "Do"


def test_text_state_operator_constants() -> None:
    assert OperatorName.SET_CHAR_SPACING == "Tc"
    assert OperatorName.SET_WORD_SPACING == "Tw"
    assert OperatorName.SET_TEXT_HORIZONTAL_SCALING == "Tz"
    assert OperatorName.SET_TEXT_LEADING == "TL"
    assert OperatorName.SET_TEXT_RENDERINGMODE == "Tr"
    assert OperatorName.SET_TEXT_RISE == "Ts"
    assert OperatorName.MOVE_TEXT == "Td"
    assert OperatorName.MOVE_TEXT_SET_LEADING == "TD"
    assert OperatorName.SET_MATRIX == "Tm"
    assert OperatorName.NEXT_LINE == "T*"
    assert OperatorName.SHOW_TEXT_LINE == "'"
    assert OperatorName.SHOW_TEXT_LINE_AND_SPACE == '"'


def test_type3_font_operator_constants() -> None:
    assert OperatorName.TYPE3_D0 == "d0"
    assert OperatorName.TYPE3_D1 == "d1"


def test_compatibility_section_operator_constants() -> None:
    assert OperatorName.BEGIN_COMPATIBILITY_SECTION == "BX"
    assert OperatorName.END_COMPATIBILITY_SECTION == "EX"


def test_clipping_operator_constants() -> None:
    assert OperatorName.CLIP_NON_ZERO == "W"
    assert OperatorName.CLIP_EVEN_ODD == "W*"


def test_curve_variant_operator_constants() -> None:
    assert OperatorName.CURVE_TO_REPLICATE_FINAL_POINT == "y"
    assert OperatorName.CURVE_TO_REPLICATE_INITIAL_POINT == "v"
    assert OperatorName.CLOSE_FILL_NON_ZERO_AND_STROKE == "b"
    assert OperatorName.CLOSE_FILL_EVEN_ODD_AND_STROKE == "b*"
    assert OperatorName.FILL_NON_ZERO_AND_STROKE == "B"
    assert OperatorName.FILL_EVEN_ODD_AND_STROKE == "B*"


def test_misc_state_operator_constants() -> None:
    assert OperatorName.SET_FLATNESS == "i"
    assert OperatorName.SET_LINE_CAPSTYLE == "J"
    assert OperatorName.SET_LINE_JOINSTYLE == "j"
    assert OperatorName.SET_LINE_DASHPATTERN == "d"
    assert OperatorName.SET_LINE_MITERLIMIT == "M"
    assert OperatorName.SET_RENDERINGINTENT == "ri"
    assert OperatorName.SHADING_FILL == "sh"


def test_class_is_not_instantiable() -> None:
    with pytest.raises(TypeError):
        OperatorName()

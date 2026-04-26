from __future__ import annotations


class OperatorName:
    """
    String constants for every PDF content-stream operator per
    ISO 32000-1 §A. Mirrors
    ``org.apache.pdfbox.contentstream.operator.OperatorName``.
    """

    # non stroking color
    NON_STROKING_COLOR: str = "sc"
    NON_STROKING_COLOR_N: str = "scn"
    NON_STROKING_RGB: str = "rg"
    NON_STROKING_GRAY: str = "g"
    NON_STROKING_CMYK: str = "k"
    NON_STROKING_COLORSPACE: str = "cs"

    # stroking color
    STROKING_COLOR: str = "SC"
    STROKING_COLOR_N: str = "SCN"
    STROKING_COLOR_RGB: str = "RG"
    STROKING_COLOR_GRAY: str = "G"
    STROKING_COLOR_CMYK: str = "K"
    STROKING_COLORSPACE: str = "CS"

    # marked content
    BEGIN_MARKED_CONTENT_SEQ: str = "BDC"
    BEGIN_MARKED_CONTENT: str = "BMC"
    END_MARKED_CONTENT: str = "EMC"
    MARKED_CONTENT_POINT_WITH_PROPS: str = "DP"
    MARKED_CONTENT_POINT: str = "MP"
    DRAW_OBJECT: str = "Do"

    # state
    CONCAT: str = "cm"
    RESTORE: str = "Q"
    SAVE: str = "q"
    SET_FLATNESS: str = "i"
    SET_GRAPHICS_STATE_PARAMS: str = "gs"
    SET_LINE_CAPSTYLE: str = "J"
    SET_LINE_DASHPATTERN: str = "d"
    SET_LINE_JOINSTYLE: str = "j"
    SET_LINE_MITERLIMIT: str = "M"
    SET_LINE_WIDTH: str = "w"
    SET_MATRIX: str = "Tm"
    SET_RENDERINGINTENT: str = "ri"

    # graphics
    APPEND_RECT: str = "re"
    BEGIN_INLINE_IMAGE: str = "BI"
    BEGIN_INLINE_IMAGE_DATA: str = "ID"
    END_INLINE_IMAGE: str = "EI"
    CLIP_EVEN_ODD: str = "W*"
    CLIP_NON_ZERO: str = "W"
    CLOSE_AND_STROKE: str = "s"
    CLOSE_FILL_EVEN_ODD_AND_STROKE: str = "b*"
    CLOSE_FILL_NON_ZERO_AND_STROKE: str = "b"
    CLOSE_PATH: str = "h"
    CURVE_TO: str = "c"
    CURVE_TO_REPLICATE_FINAL_POINT: str = "y"
    CURVE_TO_REPLICATE_INITIAL_POINT: str = "v"
    ENDPATH: str = "n"
    FILL_EVEN_ODD_AND_STROKE: str = "B*"
    FILL_EVEN_ODD: str = "f*"
    FILL_NON_ZERO_AND_STROKE: str = "B"
    FILL_NON_ZERO: str = "f"
    LEGACY_FILL_NON_ZERO: str = "F"
    LINE_TO: str = "l"
    MOVE_TO: str = "m"
    SHADING_FILL: str = "sh"
    STROKE_PATH: str = "S"

    # text
    BEGIN_TEXT: str = "BT"
    END_TEXT: str = "ET"
    MOVE_TEXT: str = "Td"
    MOVE_TEXT_SET_LEADING: str = "TD"
    NEXT_LINE: str = "T*"
    SET_CHAR_SPACING: str = "Tc"
    SET_FONT_AND_SIZE: str = "Tf"
    SET_TEXT_HORIZONTAL_SCALING: str = "Tz"
    SET_TEXT_LEADING: str = "TL"
    SET_TEXT_RENDERINGMODE: str = "Tr"
    SET_TEXT_RISE: str = "Ts"
    SET_WORD_SPACING: str = "Tw"
    SHOW_TEXT: str = "Tj"
    SHOW_TEXT_ADJUSTED: str = "TJ"
    SHOW_TEXT_LINE: str = "'"
    SHOW_TEXT_LINE_AND_SPACE: str = '"'

    # type3 font
    TYPE3_D0: str = "d0"
    TYPE3_D1: str = "d1"

    # compatibility section
    BEGIN_COMPATIBILITY_SECTION: str = "BX"
    END_COMPATIBILITY_SECTION: str = "EX"

    def __init__(self) -> None:
        # Mirrors upstream's private constructor — pure constants holder.
        raise TypeError("OperatorName is a constants holder; do not instantiate")

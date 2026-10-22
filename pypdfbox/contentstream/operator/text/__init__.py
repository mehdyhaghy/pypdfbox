from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .begin_text import BeginText
    from .end_text import EndText
    from .move_text import MoveText
    from .move_text_set_leading import MoveTextSetLeading
    from .next_line_op import NextLine
    from .set_char_spacing import SetCharSpacing
    from .set_font_and_size import SetFontAndSize
    from .set_horizontal_text_scaling import SetHorizontalTextScaling
    from .set_matrix import SetMatrix
    from .set_text_horizontal_scaling import SetTextHorizontalScaling
    from .set_text_leading_op import SetTextLeading
    from .set_text_rendering_mode_op import SetTextRenderingMode
    from .set_text_rise_op import SetTextRise
    from .set_word_spacing_op import SetWordSpacing
    from .show_text import ShowText
    from .show_text_adjusted import ShowTextAdjusted
    from .show_text_line import ShowTextLine
    from .show_text_line_and_space import ShowTextLineAndSpace

__getattr__, __dir__ = _attach(
    __name__,
    {
        "BeginText": ".begin_text",
        "EndText": ".end_text",
        "MoveText": ".move_text",
        "MoveTextSetLeading": ".move_text_set_leading",
        "NextLine": ".next_line_op",
        "SetCharSpacing": ".set_char_spacing",
        "SetFontAndSize": ".set_font_and_size",
        "SetHorizontalTextScaling": ".set_horizontal_text_scaling",
        "SetMatrix": ".set_matrix",
        "SetTextHorizontalScaling": ".set_text_horizontal_scaling",
        "SetTextLeading": ".set_text_leading_op",
        "SetTextRenderingMode": ".set_text_rendering_mode_op",
        "SetTextRise": ".set_text_rise_op",
        "SetWordSpacing": ".set_word_spacing_op",
        "ShowText": ".show_text",
        "ShowTextAdjusted": ".show_text_adjusted",
        "ShowTextLine": ".show_text_line",
        "ShowTextLineAndSpace": ".show_text_line_and_space",
    },
)

__all__ = [
    "BeginText",
    "EndText",
    "MoveText",
    "MoveTextSetLeading",
    "NextLine",
    "SetCharSpacing",
    "SetFontAndSize",
    "SetHorizontalTextScaling",
    "SetMatrix",
    "SetTextHorizontalScaling",
    "SetTextLeading",
    "SetTextRenderingMode",
    "SetTextRise",
    "SetWordSpacing",
    "ShowText",
    "ShowTextAdjusted",
    "ShowTextLine",
    "ShowTextLineAndSpace",
]

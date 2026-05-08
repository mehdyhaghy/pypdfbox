from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2


def _array(*values: int) -> COSArray:
    arr = COSArray()
    for value in values:
        arr.add(COSInteger.get(value))
    return arr


def test_set_w_invalidates_parsed_width_cache() -> None:
    font = PDCIDFontType2()
    font.set_w(_array(7, 7, 400))

    assert font.get_glyph_width(7) == 400.0

    font.set_w(_array(7, 7, 650))

    assert font.get_glyph_width(7) == 650.0


def test_set_w_none_invalidates_parsed_width_cache() -> None:
    font = PDCIDFontType2()
    font.set_w(_array(7, 7, 400))
    font.set_dw(900)

    assert font.get_glyph_width(7) == 400.0

    font.set_w(None)

    assert font.get_glyph_width(7) == 900.0


def test_set_w2_invalidates_parsed_vertical_width_cache() -> None:
    font = PDCIDFontType2()
    font.set_w2(_array(5, 5, 880, -250, -900))

    assert font.get_height(5) == 880.0
    assert font.get_position_vector(5) == (-250.0, -900.0)

    font.set_w2(_array(5, 5, 720, -200, -700))

    assert font.get_height(5) == 720.0
    assert font.get_position_vector(5) == (-200.0, -700.0)


def test_set_w2_none_invalidates_parsed_vertical_width_cache() -> None:
    font = PDCIDFontType2()
    font.set_w2(_array(5, 5, 880, -250, -900))

    assert font.get_height(5) == 880.0

    font.set_w2(None)

    assert font.get_height(5) == 0.0
    assert font.get_position_vector(5) == (500.0, 880.0)

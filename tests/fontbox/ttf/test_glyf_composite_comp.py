"""Tests for :class:`pypdfbox.fontbox.ttf.glyf_composite_comp.GlyfCompositeComp`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def test_flag_constants() -> None:
    # Values verbatim from GlyfCompositeComp.java lines 33-65.
    assert GlyfCompositeComp.ARG_1_AND_2_ARE_WORDS == 0x0001
    assert GlyfCompositeComp.ARGS_ARE_XY_VALUES == 0x0002
    assert GlyfCompositeComp.ROUND_XY_TO_GRID == 0x0004
    assert GlyfCompositeComp.WE_HAVE_A_SCALE == 0x0008
    assert GlyfCompositeComp.MORE_COMPONENTS == 0x0020
    assert GlyfCompositeComp.WE_HAVE_AN_X_AND_Y_SCALE == 0x0040
    assert GlyfCompositeComp.WE_HAVE_A_TWO_BY_TWO == 0x0080
    assert GlyfCompositeComp.WE_HAVE_INSTRUCTIONS == 0x0100
    assert GlyfCompositeComp.USE_MY_METRICS == 0x0200


def test_default_construction() -> None:
    c = GlyfCompositeComp()
    assert c.get_first_index() == 0
    assert c.get_first_contour() == 0
    assert c.get_flags() == 0
    assert c.get_glyph_index() == 0
    assert c.get_x_scale() == 1.0
    assert c.get_y_scale() == 1.0
    assert c.get_scale01() == 0.0
    assert c.get_scale10() == 0.0
    assert c.get_x_translate() == 0
    assert c.get_y_translate() == 0


def test_set_first_index_and_contour() -> None:
    c = GlyfCompositeComp()
    c.set_first_index(5)
    c.set_first_contour(2)
    assert c.get_first_index() == 5
    assert c.get_first_contour() == 2


def test_decode_byte_args_no_scale() -> None:
    # flags = ARGS_ARE_XY_VALUES (0x0002) only — args are signed bytes,
    # no scale fields trailing. glyphIndex = 0x1234, arg1 = -1, arg2 = 5.
    payload = bytes(
        [
            0x00, 0x02,  # flags
            0x12, 0x34,  # glyph index = 0x1234
            0xFF,  # arg1 = -1 (signed byte)
            0x05,  # arg2 = 5
        ]
    )
    stream = MemoryTTFDataStream(payload)
    c = GlyfCompositeComp(stream)
    assert c.get_flags() == 0x0002
    assert c.get_glyph_index() == 0x1234
    assert c.get_argument1() == -1
    assert c.get_argument2() == 5
    assert c.get_x_translate() == -1
    assert c.get_y_translate() == 5
    assert c.has_two_byte_args() is False
    assert c.args_are_xy_values() is True
    assert c.has_scale() is False
    assert c.has_xy_scale() is False
    assert c.has_two_by_two() is False
    assert c.more_components() is False


def test_decode_word_args_with_scale() -> None:
    # flags = ARG_1_AND_2_ARE_WORDS | ARGS_ARE_XY_VALUES | WE_HAVE_A_SCALE
    flags = (
        GlyfCompositeComp.ARG_1_AND_2_ARE_WORDS
        | GlyfCompositeComp.ARGS_ARE_XY_VALUES
        | GlyfCompositeComp.WE_HAVE_A_SCALE
    )
    payload = bytes(
        [
            (flags >> 8) & 0xFF, flags & 0xFF,
            0x00, 0x05,  # glyph index = 5
            0x00, 0x10,  # arg1 = 16
            0xFF, 0xF0,  # arg2 = -16
            0x40, 0x00,  # scale = 0x4000 / 0x4000 = 1.0
        ]
    )
    stream = MemoryTTFDataStream(payload)
    c = GlyfCompositeComp(stream)
    assert c.has_two_byte_args() is True
    assert c.has_scale() is True
    assert c.get_argument1() == 16
    assert c.get_argument2() == -16
    assert c.get_x_translate() == 16
    assert c.get_y_translate() == -16
    assert c.get_x_scale() == 1.0
    assert c.get_y_scale() == 1.0
    assert c.get_scale01() == 0.0
    assert c.get_scale10() == 0.0


def test_decode_xy_scale() -> None:
    flags = (
        GlyfCompositeComp.ARG_1_AND_2_ARE_WORDS
        | GlyfCompositeComp.ARGS_ARE_XY_VALUES
        | GlyfCompositeComp.WE_HAVE_AN_X_AND_Y_SCALE
    )
    payload = bytes(
        [
            (flags >> 8) & 0xFF, flags & 0xFF,
            0x00, 0x01,
            0x00, 0x00,  # arg1
            0x00, 0x00,  # arg2
            0x20, 0x00,  # xscale = 0x2000 / 0x4000 = 0.5
            0x80, 0x00,  # yscale = -0x8000 / 0x4000 = -2.0
        ]
    )
    stream = MemoryTTFDataStream(payload)
    c = GlyfCompositeComp(stream)
    assert c.has_xy_scale() is True
    assert c.get_x_scale() == 0.5
    assert c.get_y_scale() == -2.0


def test_decode_two_by_two() -> None:
    flags = (
        GlyfCompositeComp.ARG_1_AND_2_ARE_WORDS
        | GlyfCompositeComp.ARGS_ARE_XY_VALUES
        | GlyfCompositeComp.WE_HAVE_A_TWO_BY_TWO
    )
    payload = bytes(
        [
            (flags >> 8) & 0xFF, flags & 0xFF,
            0x00, 0x07,
            0x00, 0x00,
            0x00, 0x00,
            0x40, 0x00,  # xscale = 1.0
            0x20, 0x00,  # scale01 = 0.5
            0xE0, 0x00,  # scale10 = -0.5
            0x40, 0x00,  # yscale = 1.0
        ]
    )
    stream = MemoryTTFDataStream(payload)
    c = GlyfCompositeComp(stream)
    assert c.has_two_by_two() is True
    assert c.get_x_scale() == 1.0
    assert c.get_y_scale() == 1.0
    assert c.get_scale01() == 0.5
    assert c.get_scale10() == -0.5
    assert c.get_xy_scale01() == 0.5
    assert c.get_xy_scale10() == -0.5


def test_scale_x_and_y_match_java_round() -> None:
    c = GlyfCompositeComp()
    # Manually fill the matrix: xscale=2, yscale=3, scale01=0.5, scale10=-0.25.
    c._xscale = 2.0
    c._yscale = 3.0
    c._scale01 = 0.5
    c._scale10 = -0.25
    # scaleX(x,y) = round(x*xscale + y*scale10) = round(10*2 + 4*-0.25) = round(19.0) = 19
    assert c.scale_x(10, 4) == 19
    # scaleY(x,y) = round(x*scale01 + y*yscale) = round(10*0.5 + 4*3) = round(17.0) = 17
    assert c.scale_y(10, 4) == 17
    # Half-up for positives: round(1.5) = 2.
    c._xscale = 1.0
    c._scale10 = 0.0
    assert c.scale_x(1, 1) == 1
    c._xscale = 0.5
    c._scale10 = 0.0
    assert c.scale_x(3, 0) == 2  # round(1.5) = 2 (Java half-up)


def test_more_components_flag() -> None:
    c = GlyfCompositeComp()
    c._flags = GlyfCompositeComp.MORE_COMPONENTS
    assert c.more_components() is True
    c._flags = 0
    assert c.more_components() is False


def test_arg_aliases() -> None:
    c = GlyfCompositeComp()
    c._argument1 = 7
    c._argument2 = -3
    assert c.get_arg1() == 7
    assert c.get_arg2() == -3
    assert c.has_word_arg_value() is False

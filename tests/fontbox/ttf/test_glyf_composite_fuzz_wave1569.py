"""Wave 1569: fuzz the TrueType composite (compound) glyph component decoder.

Hammers :class:`GlyfCompositeComp` flag decoding, F2Dot14 scale variants,
byte-vs-word argument sizing, signed sign-extension, the 2x2 transform
matrix element order, MORE_COMPONENTS loop termination in
:class:`GlyfCompositeDescript`, point-matching (ARGS_ARE_XY_VALUES clear),
and USE_MY_METRICS predicate handling.

Every case builds synthetic ``glyf`` component bytes by hand and compares
:class:`GlyfCompositeComp` against an independent Python reference that
re-implements the OpenType ``glyf`` composite spec
(https://learn.microsoft.com/typography/opentype/spec/glyf), which is the
same algorithm Apache fontbox's ``GlyfCompositeComp`` implements.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyf_composite_descript import GlyfCompositeDescript
from pypdfbox.fontbox.ttf.random_access_read_unbuffered_data_stream import (
    RandomAccessReadUnbufferedDataStream,
)
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

# ---- flag bit constants (mirror the spec / upstream) ----------------------

ARG_1_AND_2_ARE_WORDS = 0x0001
ARGS_ARE_XY_VALUES = 0x0002
ROUND_XY_TO_GRID = 0x0004
WE_HAVE_A_SCALE = 0x0008
MORE_COMPONENTS = 0x0020
WE_HAVE_AN_X_AND_Y_SCALE = 0x0040
WE_HAVE_A_TWO_BY_TWO = 0x0080
WE_HAVE_INSTRUCTIONS = 0x0100
USE_MY_METRICS = 0x0200

F2DOT14_ONE = 0x4000  # 16384 == 1.0 in F2Dot14


# ---- byte builders --------------------------------------------------------


def _component_bytes(
    flags: int,
    glyph_index: int,
    arg1: int,
    arg2: int,
    scale_words: tuple[int, ...] = (),
) -> bytes:
    """Assemble the on-disk byte layout of one composite component.

    Layout: flags(uint16) glyphIndex(uint16) arg1 arg2 [scale words...]
    arg sizing keyed on ARG_1_AND_2_ARE_WORDS; scale words are int16
    F2Dot14 values supplied by the caller (0, 1, 2 or 4 of them).
    """
    out = struct.pack(">HH", flags & 0xFFFF, glyph_index & 0xFFFF)
    if flags & ARG_1_AND_2_ARE_WORDS:
        out += struct.pack(">hh", arg1, arg2)
    else:
        out += struct.pack(">bb", arg1, arg2)
    for w in scale_words:
        out += struct.pack(">h", w)
    return out


def _read_comp(data: bytes) -> GlyfCompositeComp:
    stream = RandomAccessReadUnbufferedDataStream(RandomAccessReadBuffer(data))
    return GlyfCompositeComp(stream)


# ---- independent reference decoder ----------------------------------------


class _RefComp:
    """Spec-faithful reference decode, independent of pypdfbox."""

    def __init__(self, data: bytes) -> None:
        off = 0
        (self.flags, self.glyph_index) = struct.unpack_from(">HH", data, off)
        off += 4
        if self.flags & ARG_1_AND_2_ARE_WORDS:
            (self.arg1, self.arg2) = struct.unpack_from(">hh", data, off)
            off += 4
        else:
            (self.arg1, self.arg2) = struct.unpack_from(">bb", data, off)
            off += 2
        self.xtranslate = self.ytranslate = 0
        self.point1 = self.point2 = 0
        if self.flags & ARGS_ARE_XY_VALUES:
            self.xtranslate, self.ytranslate = self.arg1, self.arg2
        else:
            self.point1, self.point2 = self.arg1, self.arg2
        self.xscale = self.yscale = 1.0
        self.scale01 = self.scale10 = 0.0
        if self.flags & WE_HAVE_A_SCALE:
            (i,) = struct.unpack_from(">h", data, off)
            self.xscale = self.yscale = i / float(F2DOT14_ONE)
        elif self.flags & WE_HAVE_AN_X_AND_Y_SCALE:
            (a, b) = struct.unpack_from(">hh", data, off)
            self.xscale = a / float(F2DOT14_ONE)
            self.yscale = b / float(F2DOT14_ONE)
        elif self.flags & WE_HAVE_A_TWO_BY_TWO:
            (a, b, c, d) = struct.unpack_from(">hhhh", data, off)
            self.xscale = a / float(F2DOT14_ONE)
            self.scale01 = b / float(F2DOT14_ONE)
            self.scale10 = c / float(F2DOT14_ONE)
            self.yscale = d / float(F2DOT14_ONE)


# ===========================================================================
# Flag-decode and argument-sizing cases
# ===========================================================================


@pytest.mark.parametrize(
    ("flags", "glyph_index", "arg1", "arg2"),
    [
        (ARGS_ARE_XY_VALUES, 5, 10, 20),
        (ARGS_ARE_XY_VALUES, 5, -10, -20),
        (ARGS_ARE_XY_VALUES, 5, 127, -128),  # byte extremes
        (ARGS_ARE_XY_VALUES, 5, 0, 0),
        (ARGS_ARE_XY_VALUES | ARG_1_AND_2_ARE_WORDS, 7, 1000, -1000),
        (ARGS_ARE_XY_VALUES | ARG_1_AND_2_ARE_WORDS, 7, 32767, -32768),  # word extremes
        (0, 3, 5, 9),  # point-matching, byte
        (ARG_1_AND_2_ARE_WORDS, 3, 300, 401),  # point-matching, word
    ],
    ids=[
        "xy_byte_pos",
        "xy_byte_neg",
        "xy_byte_extremes",
        "xy_byte_zero",
        "xy_word_pos_neg",
        "xy_word_extremes",
        "point_byte",
        "point_word",
    ],
)
def test_arg_sizing_and_xy_vs_point(flags, glyph_index, arg1, arg2):
    data = _component_bytes(flags, glyph_index, arg1, arg2)
    comp = _read_comp(data)
    ref = _RefComp(data)

    assert comp.get_flags() == _to_signed_short(ref.flags)
    assert comp.get_glyph_index() == ref.glyph_index
    assert comp.get_argument1() == ref.arg1
    assert comp.get_argument2() == ref.arg2
    assert comp.get_x_translate() == ref.xtranslate
    assert comp.get_y_translate() == ref.ytranslate
    assert comp.args_are_xy_values() == bool(ref.flags & ARGS_ARE_XY_VALUES)
    assert comp.has_word_arg_value() == bool(ref.flags & ARG_1_AND_2_ARE_WORDS)


def test_signed_byte_sign_extension():
    """A byte arg of 0xFF must decode to -1, not 255 (signed int8)."""
    data = _component_bytes(ARGS_ARE_XY_VALUES, 1, -1, -2)
    comp = _read_comp(data)
    assert comp.get_argument1() == -1
    assert comp.get_argument2() == -2
    assert comp.get_x_translate() == -1
    assert comp.get_y_translate() == -2


def test_word_arg_negative_sign_extension():
    data = _component_bytes(ARGS_ARE_XY_VALUES | ARG_1_AND_2_ARE_WORDS, 1, -500, -32768)
    comp = _read_comp(data)
    assert comp.get_argument1() == -500
    assert comp.get_argument2() == -32768


def test_point_matching_args_not_translates():
    """When ARGS_ARE_XY_VALUES is clear, translates stay 0 and the args
    are treated as point numbers."""
    data = _component_bytes(0, 2, 12, 34)
    comp = _read_comp(data)
    assert comp.get_x_translate() == 0
    assert comp.get_y_translate() == 0
    assert comp.get_argument1() == 12
    assert comp.get_argument2() == 34
    assert not comp.args_are_xy_values()


# ===========================================================================
# Scale-variant cases (F2Dot14 decode)
# ===========================================================================


@pytest.mark.parametrize(
    "raw",
    [F2DOT14_ONE, 0, -F2DOT14_ONE, F2DOT14_ONE // 2, 0x7FFF, -0x8000, 0x2000, -0x2000],
    ids=["one", "zero", "neg_one", "half", "max", "min", "quarter", "neg_quarter"],
)
def test_single_scale_f2dot14(raw):
    data = _component_bytes(
        ARGS_ARE_XY_VALUES | WE_HAVE_A_SCALE, 1, 0, 0, scale_words=(raw,)
    )
    comp = _read_comp(data)
    ref = _RefComp(data)
    assert comp.get_x_scale() == ref.xscale
    assert comp.get_y_scale() == ref.yscale
    assert comp.get_x_scale() == comp.get_y_scale()  # uniform
    assert comp.get_scale01() == 0.0
    assert comp.get_scale10() == 0.0
    assert comp.has_scale()


def test_single_scale_one_is_identity():
    data = _component_bytes(
        ARGS_ARE_XY_VALUES | WE_HAVE_A_SCALE, 1, 0, 0, scale_words=(F2DOT14_ONE,)
    )
    comp = _read_comp(data)
    assert comp.get_x_scale() == 1.0
    assert comp.get_y_scale() == 1.0


@pytest.mark.parametrize(
    ("xraw", "yraw"),
    [
        (F2DOT14_ONE, F2DOT14_ONE),
        (F2DOT14_ONE // 2, F2DOT14_ONE * 2 // 2),
        (-F2DOT14_ONE, F2DOT14_ONE),
        (0x2000, 0x6000),
        (0x7FFF, -0x8000),
    ],
    ids=["unit", "half_full", "flipx", "quarter_threequarter", "extremes"],
)
def test_x_and_y_scale(xraw, yraw):
    data = _component_bytes(
        ARGS_ARE_XY_VALUES | WE_HAVE_AN_X_AND_Y_SCALE,
        1,
        0,
        0,
        scale_words=(xraw, yraw),
    )
    comp = _read_comp(data)
    ref = _RefComp(data)
    assert comp.get_x_scale() == ref.xscale
    assert comp.get_y_scale() == ref.yscale
    assert comp.get_scale01() == 0.0
    assert comp.get_scale10() == 0.0
    assert comp.has_xy_scale()
    # Asymmetric inputs must NOT collapse to a single axis.
    if xraw != yraw:
        assert comp.get_x_scale() != comp.get_y_scale()


@pytest.mark.parametrize(
    ("a", "b", "c", "d"),
    [
        (F2DOT14_ONE, 0, 0, F2DOT14_ONE),  # identity
        (0x2000, 0x1000, -0x1000, 0x3000),  # arbitrary
        (-F2DOT14_ONE, 0, 0, -F2DOT14_ONE),  # 180 rotation
        (0, F2DOT14_ONE, -F2DOT14_ONE, 0),  # 90 rotation
        (0x7FFF, -0x8000, 0x4000, -0x4000),  # extremes
    ],
    ids=["identity", "arbitrary", "rot180", "rot90", "extremes"],
)
def test_two_by_two_matrix_element_order(a, b, c, d):
    """Verify the 2x2 matrix is read in spec order:
    xscale, scale01, scale10, yscale."""
    data = _component_bytes(
        ARGS_ARE_XY_VALUES | WE_HAVE_A_TWO_BY_TWO,
        1,
        0,
        0,
        scale_words=(a, b, c, d),
    )
    comp = _read_comp(data)
    ref = _RefComp(data)
    assert comp.get_x_scale() == ref.xscale
    assert comp.get_scale01() == ref.scale01
    assert comp.get_scale10() == ref.scale10
    assert comp.get_y_scale() == ref.yscale
    assert comp.has_two_by_two()
    # Off-diagonal aliases agree with primaries.
    assert comp.get_xy_scale01() == comp.get_scale01()
    assert comp.get_xy_scale10() == comp.get_scale10()


def test_no_scale_defaults_identity():
    data = _component_bytes(ARGS_ARE_XY_VALUES, 1, 4, 5)
    comp = _read_comp(data)
    assert comp.get_x_scale() == 1.0
    assert comp.get_y_scale() == 1.0
    assert comp.get_scale01() == 0.0
    assert comp.get_scale10() == 0.0
    assert not comp.has_scale()
    assert not comp.has_xy_scale()
    assert not comp.has_two_by_two()


# ===========================================================================
# Transform application (scale_x / scale_y) — matrix algebra parity
# ===========================================================================


@pytest.mark.parametrize(
    ("a", "b", "c", "d", "x", "y"),
    [
        (F2DOT14_ONE, 0, 0, F2DOT14_ONE, 100, 200),  # identity
        (0x2000, 0, 0, 0x2000, 100, 200),  # 0.5 uniform
        (0, F2DOT14_ONE, -F2DOT14_ONE, 0, 50, 70),  # 90 rotation
        (0x3000, 0x1000, -0x0800, 0x2800, 13, -27),  # skew
    ],
    ids=["identity", "halfscale", "rot90", "skew"],
)
def test_scale_x_scale_y_application(a, b, c, d, x, y):
    data = _component_bytes(
        ARGS_ARE_XY_VALUES | WE_HAVE_A_TWO_BY_TWO, 1, 0, 0, scale_words=(a, b, c, d)
    )
    comp = _read_comp(data)
    ref = _RefComp(data)
    # spec: x' = round(x*xscale + y*scale10); y' = round(x*scale01 + y*yscale)
    import math

    exp_x = math.floor(x * ref.xscale + y * ref.scale10 + 0.5)
    exp_y = math.floor(x * ref.scale01 + y * ref.yscale + 0.5)
    assert comp.scale_x(x, y) == exp_x
    assert comp.scale_y(x, y) == exp_y


def test_scale_x_uses_scale10_not_scale01():
    """Guards against transposed off-diagonal terms. With scale10 set but
    scale01 zero, scale_x must depend on y and scale_y must not."""
    # a=1, b(scale01)=0, c(scale10)=1.0, d=1
    data = _component_bytes(
        ARGS_ARE_XY_VALUES | WE_HAVE_A_TWO_BY_TWO,
        1,
        0,
        0,
        scale_words=(F2DOT14_ONE, 0, F2DOT14_ONE, F2DOT14_ONE),
    )
    comp = _read_comp(data)
    # scale_x(0, 10) = 0*1 + 10*scale10(=1) = 10
    assert comp.scale_x(0, 10) == 10
    # scale_y(0, 10) = 0*scale01(=0) + 10*1 = 10
    assert comp.scale_y(0, 10) == 10
    # scale_y(10, 0) = 10*scale01(=0) + 0 = 0  (proves scale01 is the y-row term)
    assert comp.scale_y(10, 0) == 0


def test_scale_y_uses_scale01():
    # scale01 set, scale10 zero
    data = _component_bytes(
        ARGS_ARE_XY_VALUES | WE_HAVE_A_TWO_BY_TWO,
        1,
        0,
        0,
        scale_words=(F2DOT14_ONE, F2DOT14_ONE, 0, F2DOT14_ONE),
    )
    comp = _read_comp(data)
    # scale_y(10, 0) = 10*scale01(=1) + 0 = 10
    assert comp.scale_y(10, 0) == 10
    # scale_x(0, 10) = 0 + 10*scale10(=0) = 0
    assert comp.scale_x(0, 10) == 0


@pytest.mark.parametrize(
    ("val", "expected"),
    [
        (0.5, 1),  # half rounds up
        (-0.5, 0),  # Java Math.round(-0.5) == 0 (floor(-0.5+0.5))
        (-1.5, -1),  # Java Math.round(-1.5) == -1
        (2.4, 2),
        (2.6, 3),
        (-2.4, -2),
        (-2.6, -3),
    ],
    ids=["half_up", "neg_half", "neg_three_half", "down", "up", "ndown", "nup"],
)
def test_java_round_semantics(val, expected):
    """scale_x with an identity-ish matrix exposing the rounding mode.
    Build a single-scale comp whose product equals ``val``."""
    # Use uniform scale s so that x*s == val with x=1: s = val. F2Dot14 can't
    # represent every float exactly, so instead verify the rounding helper via
    # scale_x directly with crafted xscale.
    data = _component_bytes(ARGS_ARE_XY_VALUES, 1, 0, 0)
    comp = _read_comp(data)
    comp._xscale = val  # exercise rounding only
    comp._scale10 = 0.0
    assert comp.scale_x(1, 0) == expected


# ===========================================================================
# USE_MY_METRICS / ROUND_XY_TO_GRID predicate handling
# ===========================================================================


def test_use_my_metrics_flag_preserved_in_flags():
    data = _component_bytes(
        ARGS_ARE_XY_VALUES | USE_MY_METRICS, 9, 1, 2
    )
    comp = _read_comp(data)
    assert (comp.get_flags() & USE_MY_METRICS) != 0


def test_round_xy_to_grid_flag_preserved():
    data = _component_bytes(ARGS_ARE_XY_VALUES | ROUND_XY_TO_GRID, 9, 1, 2)
    comp = _read_comp(data)
    assert (comp.get_flags() & ROUND_XY_TO_GRID) != 0


def test_more_components_predicate():
    with_more = _read_comp(
        _component_bytes(ARGS_ARE_XY_VALUES | MORE_COMPONENTS, 1, 0, 0)
    )
    without = _read_comp(_component_bytes(ARGS_ARE_XY_VALUES, 1, 0, 0))
    assert with_more.more_components()
    assert not without.more_components()


def test_has_instructions_predicate():
    comp = _read_comp(
        _component_bytes(ARGS_ARE_XY_VALUES | WE_HAVE_INSTRUCTIONS, 1, 0, 0)
    )
    assert comp.has_instructions()


# ===========================================================================
# MORE_COMPONENTS loop termination via GlyfCompositeDescript
# ===========================================================================


def _build_composite(components: list[bytes], instr: bytes = b"") -> bytes:
    return b"".join(components) + instr


def test_descript_reads_all_components_until_loop_ends():
    """Two chained components: first carries MORE_COMPONENTS, second does
    not — the loop must terminate after exactly two components."""
    c1 = _component_bytes(ARGS_ARE_XY_VALUES | MORE_COMPONENTS, 11, 5, 6)
    c2 = _component_bytes(ARGS_ARE_XY_VALUES, 22, 7, 8)
    data = _build_composite([c1, c2])
    stream = RandomAccessReadUnbufferedDataStream(RandomAccessReadBuffer(data))
    desc = GlyfCompositeDescript(stream)
    assert desc.get_component_count() == 2
    comps = desc.get_components()
    assert comps[0].get_glyph_index() == 11
    assert comps[1].get_glyph_index() == 22
    assert comps[0].more_components()
    assert not comps[1].more_components()


def test_descript_single_component():
    c1 = _component_bytes(ARGS_ARE_XY_VALUES, 33, 1, 2)
    stream = RandomAccessReadUnbufferedDataStream(RandomAccessReadBuffer(c1))
    desc = GlyfCompositeDescript(stream)
    assert desc.get_component_count() == 1


def test_descript_three_components_chain():
    c1 = _component_bytes(ARGS_ARE_XY_VALUES | MORE_COMPONENTS, 1, 0, 0)
    c2 = _component_bytes(ARGS_ARE_XY_VALUES | MORE_COMPONENTS, 2, 0, 0)
    c3 = _component_bytes(ARGS_ARE_XY_VALUES, 3, 0, 0)
    data = _build_composite([c1, c2, c3])
    stream = RandomAccessReadUnbufferedDataStream(RandomAccessReadBuffer(data))
    desc = GlyfCompositeDescript(stream)
    assert desc.get_component_count() == 3
    assert [c.get_glyph_index() for c in desc.get_components()] == [1, 2, 3]


def test_descript_consumes_instructions_after_last_component():
    """When the last component sets WE_HAVE_INSTRUCTIONS, the descript reads
    the instruction-length word + that many bytes; the stream offset must
    advance past them."""
    c1 = _component_bytes(
        ARGS_ARE_XY_VALUES | WE_HAVE_INSTRUCTIONS, 5, 1, 2
    )
    instr = struct.pack(">H", 3) + b"\x01\x02\x03"
    data = _build_composite([c1], instr)
    stream = RandomAccessReadUnbufferedDataStream(RandomAccessReadBuffer(data))
    pos_before = stream.get_original_data_size()
    desc = GlyfCompositeDescript(stream)
    assert desc.get_component_count() == 1
    # stream should have consumed component + 2-byte count + 3 instr bytes
    assert stream.get_current_position() == pos_before


def test_descript_components_view_is_immutable():
    c1 = _component_bytes(ARGS_ARE_XY_VALUES, 1, 0, 0)
    stream = RandomAccessReadUnbufferedDataStream(RandomAccessReadBuffer(c1))
    desc = GlyfCompositeDescript(stream)
    comps = desc.get_components()
    assert isinstance(comps, tuple)
    with pytest.raises((TypeError, AttributeError)):
        comps[0] = None  # type: ignore[index]


def test_descript_is_composite_and_numberofcontours():
    c1 = _component_bytes(ARGS_ARE_XY_VALUES, 1, 0, 0)
    stream = RandomAccessReadUnbufferedDataStream(RandomAccessReadBuffer(c1))
    desc = GlyfCompositeDescript(stream)
    assert desc.is_composite()


# ---- helper ---------------------------------------------------------------


def _to_signed_short(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value

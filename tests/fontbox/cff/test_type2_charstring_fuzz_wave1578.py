"""Wave 1578 fuzz/parity tests for the CFF Type 2 charstring interpreter.

Targets ``pypdfbox.fontbox.cff.type2_char_string_parser.Type2CharStringParser``
(byte-level decode + subr unrolling + hint-mask skipping) and
``pypdfbox.fontbox.cff.type2_char_string.Type2CharString`` (Type 2 -> Type 1
command-sequence conversion: width prologue, path operators, alternating
line/curve logic, flex variants, seac).

All expectations are derived from Adobe Tech Note 5177 (Type 2 Charstring
Format) and verified line-for-line against PDFBox 3.0.x
``Type2CharStringParser.java`` / ``Type2CharString.java``.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type2_char_string import Type2CharString
from pypdfbox.fontbox.cff.type2_char_string_parser import Type2CharStringParser

# Operator opcodes (TN5177 Appendix A).
HSTEM = 1
VSTEM = 3
VMOVETO = 4
RLINETO = 5
HLINETO = 6
VLINETO = 7
RRCURVETO = 8
CALLSUBR = 10
RET = 11
ENDCHAR = 14
HSTEMHM = 18
HINTMASK = 19
CNTRMASK = 20
RMOVETO = 21
HMOVETO = 22
VSTEMHM = 23
RCURVELINE = 24
RLINECURVE = 25
VVCURVETO = 26
HHCURVETO = 27
CALLGSUBR = 29
VHCURVETO = 30
HVCURVETO = 31


def _op(value: int) -> bytes:
    """Encode a single small integer operand (range -107..107 covers most
    test deltas) using the appropriate TN5177 single-/two-byte form."""
    if -107 <= value <= 107:
        return bytes([value + 139])
    if 108 <= value <= 1131:
        v = value - 108
        return bytes([247 + (v >> 8), v & 0xFF])
    if -1131 <= value <= -108:
        v = -value - 108
        return bytes([251 + (v >> 8), v & 0xFF])
    # 28: 16-bit signed
    return bytes([28]) + (value & 0xFFFF).to_bytes(2, "big")


def _names(seq: list) -> list:
    """Project a parsed sequence to operand values / operator names."""
    out = []
    for tok in seq:
        if isinstance(tok, CharStringCommand):
            out.append(tok.name)
        else:
            out.append(tok)
    return out


# ======================================================================
# Number operand encoding (read_number) — TN5177 §3.2
# ======================================================================


def test_read_number_b0_28_two_byte_signed() -> None:
    p = Type2CharStringParser("F")
    assert p.read_number(b"\x00\x64", 0, 28) == (100, 2)
    assert p.read_number(b"\xff\x9c", 0, 28) == (-100, 2)
    assert p.read_number(b"\x80\x00", 0, 28) == (-32768, 2)
    assert p.read_number(b"\x7f\xff", 0, 28) == (32767, 2)


def test_read_number_single_byte_range_32_to_246() -> None:
    p = Type2CharStringParser("F")
    assert p.read_number(b"", 0, 32) == (-107, 0)
    assert p.read_number(b"", 0, 139) == (0, 0)
    assert p.read_number(b"", 0, 246) == (107, 0)


def test_read_number_two_byte_positive_247_to_250() -> None:
    p = Type2CharStringParser("F")
    assert p.read_number(b"\x00", 0, 247) == (108, 1)
    assert p.read_number(b"\xff", 0, 250) == (1131, 1)


def test_read_number_two_byte_negative_251_to_254() -> None:
    p = Type2CharStringParser("F")
    assert p.read_number(b"\x00", 0, 251) == (-108, 1)
    assert p.read_number(b"\xff", 0, 254) == (-1131, 1)


def test_read_number_255_is_16_16_fixed_not_int32() -> None:
    # PDFBox parity: integer part = signed short; fraction = ushort / 65535.
    # 0x0001 0x8000 -> 1 + 32768/65535 ~= 1.5000038...
    p = Type2CharStringParser("F")
    val, idx = p.read_number(b"\x00\x01\x80\x00", 0, 255)
    assert idx == 4
    assert val == pytest.approx(1 + 32768 / 65535.0)
    # A value that 32-bit-int decoding would render as 98304, not 1.5.
    assert val < 2.0


def test_read_number_255_negative_integer_part() -> None:
    p = Type2CharStringParser("F")
    val, _ = p.read_number(b"\xff\xff\x00\x00", 0, 255)
    assert val == pytest.approx(-1.0)


def test_read_number_truncated_raises() -> None:
    p = Type2CharStringParser("F")
    for b0, data in ((28, b"\x00"), (247, b""), (251, b""), (255, b"\x00\x01\x80")):
        with pytest.raises(ValueError):
            p.read_number(data, 0, b0)


@pytest.mark.parametrize(
    "v",
    [0, 1, -1, 50, -50, 107, -107, 108, -108, 500, -500, 1131, -1131, 2000, -2000],
)
def test_op_roundtrip_through_parser(v: int) -> None:
    p = Type2CharStringParser("F")
    seq = p.parse(_op(v) + bytes([RMOVETO, ENDCHAR]), None, None, "g")
    assert seq[0] == v


# ======================================================================
# Subr bias — calculate_subr_number — TN5177 §4.7
# ======================================================================


@pytest.mark.parametrize(
    ("operand", "count", "expected"),
    [
        (0, 0, 107),
        (5, 100, 112),
        (-107, 50, 0),
        (0, 1239, 107),
        (0, 1240, 1131),
        (-1131, 1240, 0),
        (0, 33899, 1131),
        (0, 33900, 32768),
        (-32768, 33900, 0),
    ],
)
def test_subr_bias(operand: int, count: int, expected: int) -> None:
    assert Type2CharStringParser.calculate_subr_number(operand, count) == expected


# ======================================================================
# hint-mask byte count — get_mask_length = ceil(numStems/8)
# ======================================================================


@pytest.mark.parametrize(
    ("h", "v", "expected"),
    [
        (0, 0, 0),
        (1, 0, 1),
        (7, 0, 1),
        (8, 0, 1),
        (9, 0, 2),
        (8, 8, 2),
        (8, 9, 3),
        (16, 16, 4),
        (0, 17, 3),
    ],
)
def test_get_mask_length(h: int, v: int, expected: int) -> None:
    assert Type2CharStringParser.get_mask_length(h, v) == expected


# ======================================================================
# Stem hint counting + hintmask byte consumption (full parse)
# ======================================================================


def test_parse_hstem_count_from_operands() -> None:
    # 4 operands before hstem => 2 stem hints.
    body = _op(0) + _op(10) + _op(20) + _op(30) + bytes([HSTEM, ENDCHAR])
    seq = Type2CharStringParser("F").parse(body, None, None, "g")
    assert _names(seq) == [0, 10, 20, 30, "HSTEM", "ENDCHAR"]


def test_parse_hintmask_consumes_one_mask_byte_for_two_stems() -> None:
    # 2 hstems then hintmask with 1 mask byte.
    body = _op(0) + _op(10) + _op(20) + _op(30) + bytes([HSTEM, HINTMASK, 0xFF])
    body += _op(5) + _op(5) + bytes([RMOVETO, ENDCHAR])
    seq = Type2CharStringParser("F").parse(body, None, None, "g")
    assert _names(seq) == [0, 10, 20, 30, "HSTEM", "HINTMASK", 5, 5, "RMOVETO", "ENDCHAR"]


def test_parse_implicit_vstem_before_first_hintmask() -> None:
    # hstem (2 stems) then operands directly before hintmask are implicit
    # vstem hints: 4 operands -> +2 vstems, total 4 -> still 1 mask byte.
    body = _op(0) + _op(10) + _op(20) + _op(30) + bytes([HSTEM])
    body += _op(0) + _op(10) + _op(20) + _op(30) + bytes([HINTMASK, 0xAA])
    body += bytes([ENDCHAR])
    seq = Type2CharStringParser("F").parse(body, None, None, "g")
    # The 4 implicit-vstem operands stay in the sequence; mask byte consumed.
    assert _names(seq) == [
        0, 10, 20, 30, "HSTEM", 0, 10, 20, 30, "HINTMASK", "ENDCHAR",
    ]


def test_parse_implicit_vstem_pushes_mask_to_two_bytes() -> None:
    # 4 hstems + 12 implicit vstem operands (6 stems) = 10 stems -> 2 mask bytes.
    body = b""
    for _ in range(4):
        body += _op(1) + _op(2)
    body += bytes([HSTEMHM])
    for _ in range(6):
        body += _op(3) + _op(4)
    body += bytes([HINTMASK, 0xFF, 0x00, ENDCHAR])
    seq = Type2CharStringParser("F").parse(body, None, None, "g")
    # ENDCHAR must be reached — proves exactly 2 mask bytes were consumed.
    assert _names(seq)[-1] == "ENDCHAR"
    assert "HINTMASK" in _names(seq)


def test_parse_cntrmask_advances_like_hintmask() -> None:
    body = _op(0) + _op(10) + bytes([VSTEM, CNTRMASK, 0xFF, ENDCHAR])
    seq = Type2CharStringParser("F").parse(body, None, None, "g")
    assert _names(seq) == [0, 10, "VSTEM", "CNTRMASK", "ENDCHAR"]


def test_parse_truncated_hintmask_raises() -> None:
    # 2 stems -> 1 mask byte required, but none follow.
    body = _op(0) + _op(10) + _op(20) + _op(30) + bytes([HSTEM, HINTMASK])
    with pytest.raises(ValueError):
        Type2CharStringParser("F").parse(body, None, None, "g")


# ======================================================================
# callsubr / callgsubr with bias + nesting (RET trimming)
# ======================================================================


def test_callsubr_unrolls_and_trims_ret() -> None:
    # local subr 0 (idx 107 + bias for <1240 -> operand -107): pushes 42 then RET.
    subr = _op(42) + bytes([RET])
    lsi = [subr]
    body = _op(-107) + bytes([CALLSUBR, ENDCHAR])  # subr number 0
    seq = Type2CharStringParser("F").parse(body, None, lsi, "g")
    # 42 is inlined; RET trimmed.
    assert _names(seq) == [42, "ENDCHAR"]


def test_callgsubr_unrolls() -> None:
    gsubr = _op(7) + bytes([RET])
    gsi = [gsubr]
    body = _op(-107) + bytes([CALLGSUBR, ENDCHAR])
    seq = Type2CharStringParser("F").parse(body, gsi, None, "g")
    assert _names(seq) == [7, "ENDCHAR"]


def test_nested_callsubr() -> None:
    # subr 0 calls subr 1; subr 1 pushes 9.
    inner = _op(9) + bytes([RET])
    outer = _op(-106) + bytes([CALLSUBR, RET])  # subr number 1 (-106 + 107)
    lsi = [outer, inner]
    body = _op(-107) + bytes([CALLSUBR, ENDCHAR])  # subr number 0
    seq = Type2CharStringParser("F").parse(body, None, lsi, "g")
    assert _names(seq) == [9, "ENDCHAR"]


def test_callsubr_empty_index_is_noop() -> None:
    # No local subr index -> processCallSubr short-circuits: the CALLSUBR byte
    # is consumed and no command token is appended (mirrors upstream Java,
    # which returns without touching the sequence). The operand stays.
    body = _op(5) + bytes([CALLSUBR, ENDCHAR])
    seq = Type2CharStringParser("F").parse(body, None, None, "g")
    assert _names(seq) == [5, "ENDCHAR"]


def test_callsubr_out_of_range_returns_none_then_typeerror() -> None:
    lsi = [_op(1) + bytes([RET])]
    # subr number 5 (operand -102) -> 5 < 1, out of range high -> None -> TypeError
    body = _op(-102) + bytes([CALLSUBR, ENDCHAR])
    with pytest.raises(TypeError):
        Type2CharStringParser("F").parse(body, None, lsi, "g")


def test_callsubr_float_operand_raises_typeerror() -> None:
    lsi = [_op(1) + bytes([RET])]
    # push a 16.16 fixed (float) then callsubr -> (Integer) cast analogue raises.
    body = bytes([255, 0x00, 0x01, 0x80, 0x00]) + bytes([CALLSUBR, ENDCHAR])
    with pytest.raises(TypeError):
        Type2CharStringParser("F").parse(body, None, lsi, "g")


# ======================================================================
# Width detection in the Type 2 -> Type 1 conversion prologue
# ======================================================================


def _make_cs(nominal: float = 0.0, default: float = 0.0) -> Type2CharString:
    return Type2CharString(None, "F", "g", 0, None, default, nominal)


def test_width_consumed_on_odd_arg_first_move() -> None:
    cs = _make_cs(nominal=100.0, default=500.0)
    # rmoveto with 3 args (odd > 2) -> first arg is width delta.
    cs.convert_type1_to_type2([50, 10, 20, "rmoveto"])
    # first sequence entry should be hsbw [0, width] with width = 50 + nominal.
    seq = cs._type1_sequence
    assert seq[0] == 0
    assert seq[1] == pytest.approx(50 + 100.0)


def test_default_width_when_no_leading_operand() -> None:
    cs = _make_cs(nominal=100.0, default=500.0)
    # rmoveto with exactly 2 args -> no width, defaultWidthX used.
    cs.convert_type1_to_type2([10, 20, "rmoveto"])
    seq = cs._type1_sequence
    assert seq[0] == 0
    assert seq[1] == pytest.approx(500.0)


def test_width_on_hmoveto_odd_arg() -> None:
    cs = _make_cs(nominal=10.0, default=200.0)
    # hmoveto normally 1 arg; 2 args -> width present (flag numbers.size() > 1).
    cs.convert_type1_to_type2([77, 30, "hmoveto"])
    seq = cs._type1_sequence
    assert seq[1] == pytest.approx(77 + 10.0)


def test_width_on_first_stem_odd_arg() -> None:
    cs = _make_cs(nominal=10.0, default=200.0)
    # hstem with odd arg count -> first is width.
    cs.convert_type1_to_type2([77, 0, 10, 20, 30, "hstem", 5, 5, "rmoveto"])
    seq = cs._type1_sequence
    assert seq[1] == pytest.approx(77 + 10.0)


def test_endchar_width_with_single_arg() -> None:
    cs = _make_cs(nominal=10.0, default=200.0)
    # endchar with exactly 1 arg -> width.
    cs.convert_type1_to_type2([77, "endchar"])
    seq = cs._type1_sequence
    assert seq[1] == pytest.approx(77 + 10.0)


def test_endchar_seac_with_four_args() -> None:
    cs = _make_cs()
    # endchar with 4 args -> deprecated seac; prepends 0.
    cs.convert_type1_to_type2([1, 2, 3, 4, "endchar"])
    seq = cs._type1_sequence
    # seac arg list begins with the prepended 0.
    assert seq[0] == 0
    assert "seac" in [t for t in seq if isinstance(t, str)]


def test_endchar_seac_with_five_args_strips_width() -> None:
    cs = _make_cs(nominal=10.0)
    # 5 args -> width stripped (flag size==5), leaving 4 -> seac.
    cs.convert_type1_to_type2([77, 1, 2, 3, 4, "endchar"])
    seq = cs._type1_sequence
    # first command is hsbw with width.
    assert seq[1] == pytest.approx(77 + 10.0)
    assert "seac" in [t for t in seq if isinstance(t, str)]


# ======================================================================
# Path operator conversion -> Type 1 command sequence
# ======================================================================


def _ops_only(seq: list) -> list:
    return [t for t in seq if isinstance(t, str)]


def test_rlineto_splits_into_pairs() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2([10, 20, "rmoveto", 1, 2, 3, 4, "rlineto"])
    assert _ops_only(cs._type1_sequence).count("rlineto") == 2


def test_hlineto_alternates() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2([10, 20, "rmoveto", 1, 2, 3, "hlineto"])
    ops = _ops_only(cs._type1_sequence)
    # 3 args -> hlineto, vlineto, hlineto.
    assert ops[-3:] == ["hlineto", "vlineto", "hlineto"]


def test_vlineto_alternates_starting_vertical() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2([10, 20, "rmoveto", 1, 2, "vlineto"])
    ops = _ops_only(cs._type1_sequence)
    assert ops[-2:] == ["vlineto", "hlineto"]


def test_rrcurveto_splits_into_six_tuples() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, "rrcurveto"]
    )
    assert _ops_only(cs._type1_sequence).count("rrcurveto") == 2


def test_rcurveline() -> None:
    cs = _make_cs()
    # 6 curve args + 2 line args.
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 2, 3, 4, 5, 6, 7, 8, "rcurveline"]
    )
    ops = _ops_only(cs._type1_sequence)
    assert ops[-2:] == ["rrcurveto", "rlineto"]


def test_rlinecurve() -> None:
    cs = _make_cs()
    # 2 line args + 6 curve args.
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 2, 3, 4, 5, 6, 7, 8, "rlinecurve"]
    )
    ops = _ops_only(cs._type1_sequence)
    assert ops[-2:] == ["rlineto", "rrcurveto"]


def test_hhcurveto_emits_rrcurveto() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 2, 3, 4, "hhcurveto"]
    )
    assert "rrcurveto" in _ops_only(cs._type1_sequence)


def test_vvcurveto_emits_rrcurveto() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 2, 3, 4, "vvcurveto"]
    )
    assert "rrcurveto" in _ops_only(cs._type1_sequence)


def test_hvcurveto_alternating_control_points() -> None:
    cs = _make_cs()
    # 4 args -> single curve; horizontal start.
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 2, 3, 4, "hvcurveto"]
    )
    # Find the emitted rrcurveto args (the 6 numbers after rmoveto's command).
    seq = cs._type1_sequence
    idx = seq.index("rrcurveto")
    args = seq[idx - 6 : idx]
    # horizontal: [dx1, 0, dx2, dy2, 0, dy3]  (last==False since size==4)
    assert args == [1, 0, 2, 3, 0, 4]


def test_vhcurveto_alternating_control_points() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 2, 3, 4, "vhcurveto"]
    )
    seq = cs._type1_sequence
    idx = seq.index("rrcurveto")
    args = seq[idx - 6 : idx]
    # vertical: [0, dy1, dx2, dy2, dx3, 0]
    assert args == [0, 1, 2, 3, 4, 0]


def test_hvcurveto_with_five_args_uses_last_extra() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 2, 3, 4, 5, "hvcurveto"]
    )
    seq = cs._type1_sequence
    idx = seq.index("rrcurveto")
    args = seq[idx - 6 : idx]
    # horizontal, last==True (size==5): [dx1,0,dx2,dy2, df, dy3]
    assert args == [1, 0, 2, 3, 5, 4]


# ======================================================================
# mark_path / closepath behaviour
# ======================================================================


def test_two_moves_insert_closepath_between_subpaths() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2(
        [10, 20, "rmoveto", 1, 1, "rlineto", 5, 5, "rmoveto", 2, 2, "rlineto", "endchar"]
    )
    assert "closepath" in _ops_only(cs._type1_sequence)


def test_single_subpath_closed_on_endchar() -> None:
    cs = _make_cs()
    cs.convert_type1_to_type2([10, 20, "rmoveto", 1, 1, "rlineto", "endchar"])
    ops = _ops_only(cs._type1_sequence)
    assert "closepath" in ops
    assert ops[-1] == "endchar"


# ======================================================================
# flex variants
# ======================================================================


def test_flex_expands_to_two_rrcurveto() -> None:
    cs = _make_cs()
    args = list(range(1, 13))
    cs.convert_type1_to_type2([10, 20, "rmoveto", *args, "flex"])
    assert _ops_only(cs._type1_sequence).count("rrcurveto") == 2


def test_hflex_expands_to_two_rrcurveto() -> None:
    cs = _make_cs()
    args = [1, 2, 3, 4, 5, 6, 7]
    cs.convert_type1_to_type2([10, 20, "rmoveto", *args, "hflex"])
    ops = _ops_only(cs._type1_sequence)
    assert ops.count("rrcurveto") == 2


def test_hflex1_expands_to_two_rrcurveto() -> None:
    cs = _make_cs()
    args = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    cs.convert_type1_to_type2([10, 20, "rmoveto", *args, "hflex1"])
    assert _ops_only(cs._type1_sequence).count("rrcurveto") == 2


def test_flex1_expands_to_two_rrcurveto() -> None:
    cs = _make_cs()
    args = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    cs.convert_type1_to_type2([10, 20, "rmoveto", *args, "flex1"])
    assert _ops_only(cs._type1_sequence).count("rrcurveto") == 2


# ======================================================================
# PDFBOX-5987: num denom div collapses before the conversion walk
# ======================================================================


def test_div_triplet_collapses_to_quotient() -> None:
    cs = _make_cs()
    # 10 4 div -> 2.5 used as a move delta.
    cs.convert_type1_to_type2([10, 4, "div", 20, "rmoveto", "endchar"])
    seq = cs._type1_sequence
    # rmoveto operands: 2.5 and 20. hsbw default prefix first.
    assert 2.5 in seq


# ======================================================================
# End-to-end via fontTools-backed get_path / get_width
# ======================================================================


def test_get_width_default_when_no_prologue_width() -> None:
    # rmoveto(0 0) endchar, even arg count -> defaultWidthX.
    program = [0, 0, "rmoveto", "endchar"]
    cs = Type2CharString(None, "F", "g", 0, program, default_width_x=250, nominal_width_x=0)
    assert cs.get_width() == pytest.approx(250.0)


def test_get_width_from_leading_operand() -> None:
    # leading width operand 30 before rmoveto -> 30 + nominal.
    program = [30, 0, 0, "rmoveto", "endchar"]
    cs = Type2CharString(None, "F", "g", 0, program, default_width_x=250, nominal_width_x=100)
    assert cs.get_width() == pytest.approx(130.0)


def test_get_path_moveto_lineto() -> None:
    program = [100, 200, "rmoveto", 50, 0, "rlineto", "endchar"]
    cs = Type2CharString(None, "F", "g", 0, program, default_width_x=0, nominal_width_x=0)
    path = cs.get_path()
    tags = [c[0] for c in path]
    assert tags[0] == "moveto"
    assert "lineto" in tags

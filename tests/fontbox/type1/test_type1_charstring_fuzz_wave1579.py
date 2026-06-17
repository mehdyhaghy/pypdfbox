"""Wave 1579 — Type 1 (NOT Type 2) charstring fuzz / parity hammering.

Targets the two pure-pypdfbox Type 1 surfaces:

* ``Type1CharStringParser`` (``pypdfbox.fontbox.cff.type1_char_string_parser``)
  — the byte-level operand decoder + ``callsubr`` / ``callothersubr``
  unrolling that mirrors upstream
  ``org.apache.fontbox.cff.Type1CharStringParser`` (PDFBox 3.0.7).
* ``Type1CharString.handle_type1_command`` + the ``_RenderContext``
  interpreter shim (``pypdfbox.fontbox.cff.type1_char_string``) plus the
  fontTools-delegated ``get_path`` / ``get_width`` end-to-end render.

The cases pin behaviour that is *Type 1 specific* and diverges from Type 2:

* the Type 1 number encoding — single byte ``b0 - 139`` (32-246), the
  two two-byte forms (247-250 positive, 251-254 negative) and
  ``255 == signed 32-bit int`` (NOT the 16.16 fixed-point Type 2 uses);
* Type 1 local subrs are **unbiased** (``callsubr`` indexes ``subrs[n]``
  directly — no ``bias`` add as in Type 2);
* ``hsbw`` sets left side bearing + advance width, and the outline starts
  at the side-bearing x (sbx), not 0;
* ``sbw`` (vertical writing-mode prologue): (sbx, sby, wx, wy);
* ``div`` — float division in ``handleType1Command`` (``a / b``) and the
  integer division ``removeInteger`` uses for othersubr operands
  (``b // a``);
* ``seac`` accent placement formula ``(lsb.x + adx - asb, lsb.y + ady)``;
* the flex / hint-replacement OtherSubrs (0 end-flex, 1 begin-flex,
  3 hint-replacement) and the immediately-following ``pop`` peel loop;
* path operators (rlineto/hlineto/vlineto, rrcurveto/vhcurveto/hvcurveto,
  rmoveto/hmoveto/vmoveto, closepath) and ``hstem`` / ``vstem`` /
  ``hstem3`` / ``vstem3`` / ``dotsection`` (hints, ignored for outline).

Values verified against the Adobe Type 1 Font Format spec (Tech Note 5040)
and a read of the PDFBox 3.0.7 Java sources.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type1_char_string import Type1CharString, _RenderContext
from pypdfbox.fontbox.cff.type1_char_string_parser import Type1CharStringParser
from pypdfbox.fontbox.cff.type1_keyword import Type1KeyWord


def _parse(data: bytes, subrs: list[bytes] | None = None) -> list[Any]:
    return Type1CharStringParser("Fuzz").parse(data, subrs or [], "glyph")


def _ops(seq: list[Any]) -> list[Any]:
    """Map a parsed sequence to ints and operator mnemonics for comparison."""
    out: list[Any] = []
    for tok in seq:
        if isinstance(tok, CharStringCommand):
            kw = tok.get_type1_key_word()
            out.append(kw.name if kw is not None else "?")
        else:
            out.append(tok)
    return out


# --------------------------------------------------------------------------
# Type 1 number encoding — distinct from Type 2 (255 == int32, not 16.16)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (bytes([32]), -107),       # 32 - 139
        (bytes([139]), 0),         # 139 - 139
        (bytes([246]), 107),       # 246 - 139
        (bytes([247, 0]), 108),    # (247-247)*256 + 0 + 108
        (bytes([250, 255]), 1131),  # (250-247)*256 + 255 + 108
        (bytes([251, 0]), -108),   # -(251-251)*256 - 0 - 108
        (bytes([254, 255]), -1131),  # -(254-251)*256 - 255 - 108
    ],
    ids=[
        "b32_neg107", "b139_zero", "b246_107",
        "two_byte_pos_min", "two_byte_pos_max",
        "two_byte_neg_min", "two_byte_neg_max",
    ],
)
def test_number_encoding_single_and_two_byte(
    data: bytes, expected: int
) -> None:
    assert _parse(data) == [expected]


@pytest.mark.parametrize(
    "value",
    [0, 1, -1, 1000, -1000, 65536, -65536, 2147483647, -2147483648, 100000],
    ids=[
        "zero", "one", "neg_one", "k", "neg_k",
        "exactly_65536", "neg_65536", "int32_max", "int32_min", "hundred_k",
    ],
)
def test_number_encoding_255_is_signed_int32_not_fixed_point(
    value: int,
) -> None:
    # The defining Type 1 vs Type 2 divergence: byte 255 introduces a raw
    # signed 32-bit big-endian integer. A Type 2 reader would treat the
    # same four bytes as 16.16 fixed-point (value / 65536). Confirm we
    # decode the integer, NOT the fixed-point value.
    data = bytes([255]) + value.to_bytes(4, "big", signed=True)
    assert _parse(data) == [value]


def test_number_255_not_divided_by_65536() -> None:
    # 65536 encoded as int32 must stay 65536, not collapse to 1.0 (which is
    # what 16.16 fixed-point decoding would yield).
    data = bytes([255, 0x00, 0x01, 0x00, 0x00])
    (result,) = _parse(data)
    assert result == 65536
    assert result != 1


# --------------------------------------------------------------------------
# hsbw / sbw — side bearing + advance width prologue
# --------------------------------------------------------------------------


def test_hsbw_parsed_as_two_operands_then_command() -> None:
    # 40 hsbw_width=700: 40 -> 179, 700 -> 247-form: (700-108)=592 ->
    # 592//256 = 2 -> b0 = 249, b1 = 592 - 512 = 80.
    data = bytes([179, 249, 80, 13])
    assert _ops(_parse(data)) == [40, 700, "HSBW"]


def test_hsbw_sets_sidebearing_and_width_and_start_x() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [40, 700], "hsbw")
    assert ctx.left_side_bearing == (40.0, 0.0)
    assert ctx.width == 700
    # Outline begins at the side-bearing x (Adobe Type 1 spec §6.4).
    assert ctx.current == (40.0, 0.0)


def test_hsbw_then_rmoveto_starts_path_at_sidebearing() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [50, 600], "hsbw")
    cs.handle_type1_command(ctx, [100, 200], "rmoveto")
    # 50 (sbx) + 100 (dx) == 150 ; the sidebearing IS the start x.
    assert ctx.path == [("moveto", 150.0, 200.0)]


def test_sbw_sets_both_sidebearings_and_width() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [40, 10, 700, 0], "sbw")
    assert ctx.left_side_bearing == (40.0, 10.0)
    assert ctx.width == 700
    assert ctx.current == (40.0, 10.0)


def test_hsbw_width_through_fonttools_render() -> None:
    prog = [50, 600, "hsbw", 100, 200, "rmoveto", 300, "hlineto",
            "closepath", "endchar"]
    cs = Type1CharString(None, "F", "A", prog)
    assert cs.get_width() == 600.0
    path = cs.get_path()
    assert path[0] == ("moveto", 150.0, 200.0)  # sbx (50) + dx (100)
    assert ("lineto", 450.0, 200.0) in path     # +300 horizontal


# --------------------------------------------------------------------------
# Unbiased subrs (Type 1) — distinct from Type 2's bias
# --------------------------------------------------------------------------


def test_callsubr_is_unbiased_index_zero() -> None:
    subr0 = bytes([144, 145, 5])  # 5 6 rlineto
    main = bytes([139, 10])       # 0 callsubr
    assert _ops(_parse(main, [subr0])) == [5, 6, "RLINETO"]


def test_callsubr_is_unbiased_index_two() -> None:
    subrs = [bytes([13]), bytes([13]), bytes([144, 145, 5])]
    main = bytes([141, 10])  # 2 callsubr -> subrs[2] directly (no +bias)
    assert _ops(_parse(main, subrs)) == [5, 6, "RLINETO"]


def test_callsubr_out_of_range_strips_operands() -> None:
    # operand 61, no subrs -> upstream warns and drops trailing ints.
    assert _parse(bytes([200, 10])) == []


def test_callsubr_strips_trailing_return() -> None:
    # subr ends with RET; the unroll pops it after inlining.
    subr0 = bytes([139, 11])  # 0 return
    main = bytes([139, 10])   # 0 callsubr
    assert _ops(_parse(main, [subr0])) == [0]


def test_callsubr_non_integer_operand_dropped() -> None:
    # A command (not an int) before callsubr -> upstream pops it, warns,
    # and returns, so the command is removed from the sequence entirely.
    main = bytes([1, 10])  # hstem callsubr
    assert _ops(_parse(main, [bytes([13])])) == []


# --------------------------------------------------------------------------
# div — float in handle_type1_command, int in removeInteger
# --------------------------------------------------------------------------


def test_div_in_handle_command_is_float_division() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    n = [10, 4]
    cs.handle_type1_command(ctx, n, "div")
    assert n == [2.5]  # a / b == 10 / 4 (float, matches upstream)


def test_div_in_handle_command_negative() -> None:
    cs = Type1CharString(None, "F", "A", None)
    n = [-9, 2]
    cs.handle_type1_command(_RenderContext(), n, "div")
    assert n == [-4.5]


def test_div_in_removeinteger_is_integer_division() -> None:
    # 10 2 div consumed as an othersubr operand: removeInteger does b // a.
    data = bytes([149, 141, 12, 12, 140, 144, 12, 16, 12, 17, 11])
    # 10 2 div 1 5 callothersubr pop return
    assert _ops(_parse(data)) == [5, "RET"]


def test_div_removeinteger_truncates_toward_negative() -> None:
    # -7 2 div -> Python b // a == -7 // 2 == -4 (floor), matching Java
    # integer division? Java truncates toward zero (-3). We mirror upstream
    # b // a (floor); pin our actual behaviour so a future change is caught.
    parser = Type1CharStringParser("F")
    seq: list[Any] = [-7, 2, CharStringCommand.COMMAND_DIV]
    assert parser.remove_integer(seq) == -7 // 2


def test_div_removeinteger_exact() -> None:
    parser = Type1CharStringParser("F")
    seq: list[Any] = [12, 4, CharStringCommand.COMMAND_DIV]
    assert parser.remove_integer(seq) == 3


# --------------------------------------------------------------------------
# callothersubr — flex (0/1) + hint replacement (3) + pop peel
# --------------------------------------------------------------------------


def test_othersubr_1_begin_flex_emits_one_callothersubr() -> None:
    # 0 1 callothersubr return  (numArgs=0, othersubrNum=1)
    data = bytes([139, 140, 12, 16, 11])
    assert _ops(_parse(data)) == [1, "CALLOTHERSUBR", "RET"]


def test_othersubr_0_end_flex_emits_zero_callothersubr() -> None:
    # 0 0 3 0 callothersubr return : two operands + extra, num=0.
    data = bytes([139, 139, 142, 139, 12, 16, 11])
    assert _ops(_parse(data)) == [0, "CALLOTHERSUBR", "RET"]


def test_othersubr_3_hint_replacement_pushes_subr_via_pop() -> None:
    # subr#=3 numArgs=1 othersubrNum=3 callothersubr pop return.
    data = bytes([142, 140, 142, 12, 16, 12, 17, 11])
    # the popped result (subr number 3) is pushed back before RET.
    assert _ops(_parse(data)) == [3, "RET"]


def test_othersubr_pop_peel_requires_trailing_bytes() -> None:
    # callothersubr must be followed by the bytes the pop-peek reads;
    # a truncated charstring whose callothersubr ends the buffer raises
    # (upstream peekUnsignedByte throws IOException -> OSError here).
    data = bytes([139, 140, 12, 16])  # 0 1 callothersubr <EOF>
    with pytest.raises(OSError):
        _parse(data)


def test_othersubr_default_pops_numargs_operands() -> None:
    # numArgs=2, othersubrNum=99 (default): pops 2 ints, two pops peel them.
    # 11 22 2 99 callothersubr pop pop return
    data = bytes([
        150, 161, 141, 238,  # 11 22 2 99
        12, 16,              # callothersubr
        12, 17, 12, 17,      # pop pop
        11,                  # return
    ])
    out = _ops(_parse(data))
    # both operands peeled back (LIFO): 11 then 22.
    assert out == [11, 22, "RET"]


def test_flex_begin_sets_is_flex_in_shim() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.call_other_subr(ctx, 1)
    assert ctx.is_flex is True


def test_flex_end_with_seven_points_emits_two_curves() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    # Establish a current point first (an initial moveto) — otherwise the
    # first rrcurveTo degrades to a moveto per upstream's "rrcurveTo without
    # initial moveTo" recovery and only one curve survives.
    cs.handle_type1_command(ctx, [0, 0], "hsbw")
    cs.rmove_to(ctx, 100, 100)
    cs.call_other_subr(ctx, 1)
    # 7 flex collection points.
    for pt in [(0, 5), (10, 0), (10, 0), (10, 0), (10, 0), (10, 0), (10, 0)]:
        ctx.flex_points.append((float(pt[0]), float(pt[1])))
    cs.call_other_subr(ctx, 0)
    assert ctx.is_flex is False
    curves = [c for c in ctx.path if c[0] == "curveto"]
    assert len(curves) == 2


def test_flex_end_too_few_points_is_noop() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.call_other_subr(ctx, 1)
    ctx.flex_points.append((1.0, 1.0))  # only one
    cs.call_other_subr(ctx, 0)
    assert ctx.path == []
    assert ctx.flex_points == []


# --------------------------------------------------------------------------
# Path operators
# --------------------------------------------------------------------------


def test_rlineto_hlineto_vlineto_relative() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [0, 0], "hsbw")
    cs.handle_type1_command(ctx, [10, 10], "rmoveto")
    cs.handle_type1_command(ctx, [5, 7], "rlineto")
    cs.handle_type1_command(ctx, [3], "hlineto")
    cs.handle_type1_command(ctx, [4], "vlineto")
    assert ctx.path == [
        ("moveto", 10.0, 10.0),
        ("lineto", 15.0, 17.0),
        ("lineto", 18.0, 17.0),  # hlineto: +3 x only
        ("lineto", 18.0, 21.0),  # vlineto: +4 y only
    ]


def test_rrcurveto_vhcurveto_hvcurveto() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [0, 0], "hsbw")
    cs.handle_type1_command(ctx, [0, 0], "rmoveto")
    cs.handle_type1_command(ctx, [10, 0, 10, 10, 0, 10], "rrcurveto")
    # current now (20, 20)
    assert ctx.path[-1] == ("curveto", 10.0, 0.0, 20.0, 10.0, 20.0, 20.0)
    cs.handle_type1_command(ctx, [5, 5, 5, 5], "vhcurveto")
    # vhcurveto -> rrcurveTo(0, n0, n1, n2, n3, 0)
    last = ctx.path[-1]
    assert last[0] == "curveto"
    cs.handle_type1_command(ctx, [6, 6, 6, 6], "hvcurveto")
    assert ctx.path[-1][0] == "curveto"


def test_rmoveto_hmoveto_vmoveto() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [0, 0], "hsbw")
    cs.handle_type1_command(ctx, [10, 20], "rmoveto")
    cs.handle_type1_command(ctx, [5], "hmoveto")
    cs.handle_type1_command(ctx, [7], "vmoveto")
    assert ctx.path == [
        ("moveto", 10.0, 20.0),
        ("moveto", 15.0, 20.0),
        ("moveto", 15.0, 27.0),
    ]


def test_closepath_emits_close_then_moveto() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [0, 0], "hsbw")
    cs.handle_type1_command(ctx, [10, 10], "rmoveto")
    cs.handle_type1_command(ctx, [5, 0], "rlineto")
    cs.handle_type1_command(ctx, [], "closepath")
    assert ctx.path[-2] == ("closepath",)
    assert ctx.path[-1] == ("moveto", 15.0, 10.0)


# --------------------------------------------------------------------------
# Hints — parsed, ignored for the outline
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "op", ["hstem", "vstem", "hstem3", "vstem3", "dotsection"],
    ids=["hstem", "vstem", "hstem3", "vstem3", "dotsection"],
)
def test_hints_do_not_alter_path(op: str) -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [0, 0], "hsbw")
    before = list(ctx.path)
    cs.handle_type1_command(ctx, [0, 10, 20, 30], op)
    assert ctx.path == before


def test_hstem3_vstem3_parse_as_escape_ops() -> None:
    # 12 2 == HSTEM3, 12 1 == VSTEM3.
    assert _ops(_parse(bytes([12, 2]))) == ["HSTEM3"]
    assert _ops(_parse(bytes([12, 1]))) == ["VSTEM3"]
    assert _ops(_parse(bytes([12, 0]))) == ["DOTSECTION"]


# --------------------------------------------------------------------------
# seac — Standard Encoding Accented Character composite
# --------------------------------------------------------------------------


class _StubComponent:
    def __init__(self, path: list[tuple[Any, ...]]) -> None:
        self._path = path

    def get_path(self) -> list[tuple[Any, ...]]:
        return list(self._path)


class _StubReader:
    """Resolves seac component glyphs by StandardEncoding name."""

    def __init__(self) -> None:
        self.requested: list[str] = []

    def get_type1_char_string(self, name: str) -> _StubComponent:
        self.requested.append(name)
        # base = "A" (code 65), accent = "grave" (code 96 in StdEnc).
        return _StubComponent([("moveto", 0.0, 0.0), ("lineto", 10.0, 0.0)])


def test_seac_translates_accent_by_lsb_adx_asb_ady() -> None:
    reader = _StubReader()
    cs = Type1CharString(reader, "F", "Agrave", None)
    ctx = _RenderContext()
    ctx.left_side_bearing = (40.0, 0.0)
    # asb=20, adx=70, ady=15, bchar=65 (A), achar=96 (grave)
    cs.seac(ctx, 20, 70, 15, 65, 96)
    # accent translation tx = lsb.x + adx - asb = 40 + 70 - 20 = 90 ; ty = 15
    assert ("moveto", 0.0, 0.0) in ctx.path        # base, untranslated
    assert ("moveto", 90.0, 15.0) in ctx.path      # accent, translated
    assert ("lineto", 100.0, 15.0) in ctx.path


def test_seac_accent_offset_uses_lsb_y() -> None:
    reader = _StubReader()
    cs = Type1CharString(reader, "F", "Agrave", None)
    ctx = _RenderContext()
    ctx.left_side_bearing = (5.0, 3.0)
    cs.seac(ctx, 0, 0, 0, 65, 96)
    # tx = 5 + 0 - 0 = 5 ; ty = 3 + 0 = 3.
    assert ("moveto", 5.0, 3.0) in ctx.path


def test_seac_no_reader_is_noop() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.seac(ctx, 0, 0, 0, 65, 96)
    assert ctx.path == []


def test_seac_self_recursion_guarded() -> None:
    # A reader returning ``cs`` itself for the accent must not recurse.
    cs = Type1CharString.__new__(Type1CharString)

    class _SelfReader:
        def get_type1_char_string(self, name: str) -> Any:
            return cs

    Type1CharString.__init__(cs, _SelfReader(), "F", "A", None)
    ctx = _RenderContext()
    # Should return without raising / infinite recursion.
    cs.seac(ctx, 0, 0, 0, 65, 96)


# --------------------------------------------------------------------------
# setcurrentpoint
# --------------------------------------------------------------------------


def test_setcurrentpoint_sets_absolute_without_moveto() -> None:
    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [123, 456], "setcurrentpoint")
    assert ctx.current == (123.0, 456.0)
    assert ctx.path == []  # no path command emitted


# --------------------------------------------------------------------------
# Parser structural — keyword identity + escape decoding
# --------------------------------------------------------------------------


def test_seac_sbw_decoded_as_escape_ops() -> None:
    assert _ops(_parse(bytes([12, 6]))) == ["SEAC"]
    assert _ops(_parse(bytes([12, 7]))) == ["SBW"]
    assert _ops(_parse(bytes([12, 33]))) == ["SETCURRENTPOINT"]


def test_div_keyword_is_escape_12_12() -> None:
    (cmd,) = _parse(bytes([12, 12]))
    assert cmd.get_type1_key_word() is Type1KeyWord.DIV


def test_truncated_escape_raises() -> None:
    # A two-byte escape prefix with no second byte raises (upstream
    # readUnsignedByte throws IOException -> OSError).
    with pytest.raises(OSError):
        _parse(bytes([12]))


def test_truncated_255_operand_raises() -> None:
    # byte 255 needs 4 follow-up bytes.
    with pytest.raises(OSError):
        _parse(bytes([255, 0, 0]))


def test_empty_charstring_parses_to_empty() -> None:
    assert _parse(b"") == []

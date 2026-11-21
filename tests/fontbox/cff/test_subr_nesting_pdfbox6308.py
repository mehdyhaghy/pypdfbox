"""PDFBOX-6308: subroutine nesting limit in the Type 1 / Type 2 charstring
parsers, plus regression tests for the fontTools-delegated glyph paths that
render CFF and Type 1 outlines."""

import io
import time

import pytest
from fontTools.cffLib import SubrsIndex
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.psCharStrings import T1CharString, T2CharString

from pypdfbox.fontbox.cff import type1_char_string_parser, type2_char_string_parser
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cff.type1_char_string import Type1CharString
from pypdfbox.fontbox.cff.type1_char_string_parser import Type1CharStringParser
from pypdfbox.fontbox.cff.type2_char_string_parser import Type2CharStringParser

CALLSUBR = 10
RETURN = 11
ENDCHAR = 14
RMOVETO = 21
T1_NUMBER_0 = 139
T2_SUBR_0 = 32
NUMBER_100 = 239


def test_limits_match_upstream_final_values() -> None:
    # 623faba8 introduced 20; 0c0bed57 / 3f20d6bc raised it; c318bc89 lowered
    # the Type 1 value only.
    assert Type1CharStringParser.MAX_SUBR_NESTING == 106
    assert type1_char_string_parser.MAX_SUBR_NESTING == 106
    assert Type2CharStringParser.MAX_SUBR_NESTING == 150
    assert type2_char_string_parser.MAX_SUBR_NESTING == 150


def test_type1_error_message_names_glyph_and_font() -> None:
    loop = bytes([T1_NUMBER_0, CALLSUBR])
    with pytest.raises(OSError, match=r"nested more than 106 levels deep in glyph 'g' of font F"):
        Type1CharStringParser("F").parse(loop, [loop], "g")


def test_type1_nesting_is_depth_not_call_count() -> None:
    # Many sequential calls at depth 1 are fine: Type 1 counts depth.
    subr = bytes([NUMBER_100, RETURN])
    program = bytes([T1_NUMBER_0, CALLSUBR] * 200 + [ENDCHAR])
    seq = Type1CharStringParser("F").parse(program, [subr], "g")
    assert seq.count(100) == 200


def test_type2_error_message_names_font() -> None:
    loop = bytes([T2_SUBR_0, CALLSUBR])
    with pytest.raises(OSError, match=r"nested more than 150 levels deep in font F"):
        Type2CharStringParser("F").parse(loop, [], [loop], "g")


def test_type2_counter_is_cumulative_like_upstream() -> None:
    # Upstream increments GlyphData.subrNesting per call and never
    # decrements it, so 151 sequential calls in one glyph exceed the limit.
    subr = bytes([NUMBER_100, RETURN])
    ok = bytes([T2_SUBR_0, CALLSUBR] * 150 + [ENDCHAR])
    assert Type2CharStringParser("F").parse(ok, [], [subr], "g").count(100) == 150
    too_many = bytes([T2_SUBR_0, CALLSUBR] * 151 + [ENDCHAR])
    with pytest.raises(OSError):
        Type2CharStringParser("F").parse(too_many, [], [subr], "g")


def test_type2_counter_resets_per_parse() -> None:
    subr = bytes([NUMBER_100, RETURN])
    program = bytes([T2_SUBR_0, CALLSUBR] * 100 + [ENDCHAR])
    parser = Type2CharStringParser("F")
    parser.parse(program, [], [subr], "a")
    assert parser.parse(program, [], [subr], "b").count(100) == 100


# ---------------------------------------------------------------------------
# Lib-delegated paths: glyph outlines and widths are interpreted by fontTools.
# fontTools has no nesting limit of its own; endless recursion is stopped by
# Python's recursion limit and the wrappers return an empty path / zero width
# instead of raising or hanging.
# ---------------------------------------------------------------------------


def _build_cff(subr_programs: list[bytes], glyph_program: bytes) -> bytes:
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "A"])
    fb.setupCharacterMap({0x41: "A"})
    notdef = T2CharString()
    notdef.program = ["endchar"]
    glyph = T2CharString()
    glyph.program = ["endchar"]
    fb.setupCFF(
        psName="T",
        fontInfo={},
        charStringsDict={".notdef": notdef, "A": glyph},
        privateDict={},
    )
    cff = fb.font["CFF "].cff
    top = cff.topDictIndex[0]
    subrs = SubrsIndex()
    for program in subr_programs:
        subrs.append(T2CharString(bytecode=program))
    top.Private.Subrs = subrs
    cs = top.CharStrings["A"]
    cs.bytecode = glyph_program
    cs.program = None
    # the bbox recalculation would itself recurse without bound
    fb.font.recalcBBoxes = False
    buf = io.BytesIO()
    cff.compile(buf, fb.font, isCFF2=False)
    return buf.getvalue()


_CALL_SUBR_0 = bytes([T2_SUBR_0, CALLSUBR, ENDCHAR])


@pytest.mark.parametrize(
    "subrs",
    [
        [bytes([T2_SUBR_0, CALLSUBR])],
        [bytes([T2_SUBR_0 + 1, CALLSUBR]), bytes([T2_SUBR_0, CALLSUBR])],
    ],
    ids=["self", "mutual"],
)
def test_cff_glyph_with_recursive_subrs_is_empty(subrs: list[bytes]) -> None:
    font = CFFType1Font.from_bytes(_build_cff(subrs, _CALL_SUBR_0))
    start = time.monotonic()
    assert font.get_path("A") == []
    assert font.get_width("A") == 0
    cs = font.get_type2_char_string(1)
    assert cs.get_path() == []
    assert cs.get_width() == 0
    assert time.monotonic() - start < 10


def test_cff_glyph_nested_to_upstream_limit_renders() -> None:
    n = Type2CharStringParser.MAX_SUBR_NESTING
    subrs = [bytes([T2_SUBR_0 + i, CALLSUBR, RETURN]) for i in range(1, n)]
    subrs.append(bytes([NUMBER_100, NUMBER_100, RMOVETO, RETURN]))
    font = CFFType1Font.from_bytes(_build_cff(subrs, _CALL_SUBR_0))
    assert font.get_path("A")[0] == ("moveto", 100.0, 100.0)


def _type1(subrs: list[bytes]) -> Type1CharString:
    # hsbw 0 0, callsubr 0, endchar
    cs = T1CharString(
        bytecode=bytes([T1_NUMBER_0, T1_NUMBER_0, 13, T1_NUMBER_0, CALLSUBR, ENDCHAR]),
        subrs=[T1CharString(bytecode=s) for s in subrs],
    )
    return Type1CharString(None, "T", "a", cs)


@pytest.mark.parametrize(
    "subrs",
    [
        [bytes([T1_NUMBER_0, CALLSUBR])],
        [bytes([T1_NUMBER_0 + 1, CALLSUBR]), bytes([T1_NUMBER_0, CALLSUBR])],
    ],
    ids=["self", "mutual"],
)
def test_type1_glyph_with_recursive_subrs_is_empty(subrs: list[bytes]) -> None:
    cs = _type1(subrs)
    assert cs.get_path() == []
    assert cs.get_width() == 0


def test_type1_glyph_nested_to_upstream_limit_renders() -> None:
    n = Type1CharStringParser.MAX_SUBR_NESTING
    subrs = [bytes([T1_NUMBER_0 + i, CALLSUBR, RETURN]) for i in range(1, n)]
    subrs.append(bytes([NUMBER_100, NUMBER_100, RMOVETO, RETURN]))
    assert _type1(subrs).get_path()[0] == ("moveto", 100.0, 100.0)

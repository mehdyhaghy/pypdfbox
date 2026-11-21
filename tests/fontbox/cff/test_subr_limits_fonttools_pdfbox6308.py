"""PDFBOX-6308 limits on the fontTools-backed charstring interpreters.

pypdfbox draws glyphs and reads advance widths through fontTools'
charstring extractors rather than the ported ``Type1CharStringParser`` /
``Type2CharStringParser``. These tests pin that every such path enforces the
upstream limits with the upstream outcome: a glyph inside the limit renders,
a glyph over it raises ``OSError`` with the upstream message (upstream throws
``IOException`` from ``getType2CharString`` / ``getType1CharString``).

* Type 2: at most 150 ``callsubr`` + ``callgsubr`` calls per glyph, counted
  cumulatively (``GlyphData.subrNesting`` is never decremented).
* Type 1: ``callsubr`` nests at most 106 levels deep.
"""

import io

import pytest
from fontTools.cffLib import SubrsIndex
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.psCharStrings import T1CharString, T2CharString
from fontTools.pens.recordingPen import RecordingPen

from pypdfbox.fontbox.cff._subr_limits import (
    LimitedGlyphSet,
    SubrLimitError,
    limited_glyph_set,
)
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cff.type1_char_string import Type1CharString
from pypdfbox.fontbox.cff.type1_char_string_parser import MAX_SUBR_NESTING as T1_MAX
from pypdfbox.fontbox.cff.type2_char_string_parser import MAX_SUBR_NESTING as T2_MAX
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

CALLSUBR = 10
RETURN = 11
ENDCHAR = 14
RMOVETO = 21
CALLGSUBR = 29
# Type 2 operand byte for subr i when the index holds < 1240 entries
# (bias 107): the value i - 107 encodes as the single byte i + 32.
T2_SUBR_0 = 32
NUMBER_100 = 239

T2_MSG = r"Subroutines are nested more than 150 levels deep in font T"


def test_limits_are_the_final_upstream_values() -> None:
    assert T1_MAX == 106
    assert T2_MAX == 150


# ---------------------------------------------------------------------------
# Type 2 (CFF)
# ---------------------------------------------------------------------------


def _fontbuilder(
    glyphs: dict[str, bytes],
    local_subrs: list[bytes],
    global_subrs: list[bytes] | None = None,
) -> FontBuilder:
    order = [".notdef", *glyphs]
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x41 + i: name for i, name in enumerate(glyphs)})
    placeholders = {}
    for name in order:
        cs = T2CharString()
        cs.program = ["endchar"]
        placeholders[name] = cs
    fb.setupCFF(
        psName="T", fontInfo={}, charStringsDict=placeholders, privateDict={}
    )
    cff = fb.font["CFF "].cff
    top = cff.topDictIndex[0]
    if local_subrs:
        subrs = SubrsIndex()
        for program in local_subrs:
            subrs.append(T2CharString(bytecode=program))
        top.Private.Subrs = subrs
    for program in global_subrs or []:
        cff.GlobalSubrs.append(T2CharString(bytecode=program))
    for name, program in glyphs.items():
        cs = top.CharStrings[name]
        cs.bytecode = program
        cs.program = None
    # bbox recalculation would interpret the glyphs without a limit
    fb.font.recalcBBoxes = False
    return fb


def _build_cff(
    glyphs: dict[str, bytes],
    local_subrs: list[bytes],
    global_subrs: list[bytes] | None = None,
) -> bytes:
    fb = _fontbuilder(glyphs, local_subrs, global_subrs)
    buf = io.BytesIO()
    fb.font["CFF "].cff.compile(buf, fb.font, isCFF2=False)
    return buf.getvalue()


def _chain(length: int, op: int = CALLSUBR) -> list[bytes]:
    """Subrs where each calls the next and the last one moves to 100 100."""
    subrs = [bytes([T2_SUBR_0 + i, op, RETURN]) for i in range(1, length)]
    subrs.append(bytes([NUMBER_100, NUMBER_100, RMOVETO, RETURN]))
    return subrs


def _call(op: int = CALLSUBR) -> bytes:
    return bytes([T2_SUBR_0, op, ENDCHAR])


def _font(**kwargs: object) -> CFFType1Font:
    return CFFType1Font.from_bytes(_build_cff(**kwargs))  # type: ignore[arg-type]


def test_type2_chain_at_limit_renders() -> None:
    font = _font(glyphs={"A": _call()}, local_subrs=_chain(T2_MAX))
    assert font.get_path("A")[0] == ("moveto", 100.0, 100.0)
    assert font.get_width("A") == 0.0
    cs = font.get_type2_char_string(1)
    assert cs.get_path()[0] == ("moveto", 100.0, 100.0)
    assert cs.get_width() == 0.0


def test_type2_chain_over_limit_raises() -> None:
    font = _font(glyphs={"A": _call()}, local_subrs=_chain(T2_MAX + 1))
    with pytest.raises(OSError, match=T2_MSG):
        font.get_path("A")
    with pytest.raises(OSError, match=T2_MSG):
        font.get_width("A")
    cs = font.get_type2_char_string(1)
    with pytest.raises(OSError, match=T2_MSG):
        cs.get_path()
    with pytest.raises(OSError, match=T2_MSG):
        cs.get_width()


def test_type2_limit_error_is_an_oserror_subclass() -> None:
    font = _font(glyphs={"A": _call()}, local_subrs=_chain(T2_MAX + 1))
    with pytest.raises(SubrLimitError) as info:
        font.get_path("A")
    assert isinstance(info.value, OSError)


def test_type2_global_chain_is_limited_too() -> None:
    ok = _font(
        glyphs={"A": _call(CALLGSUBR)},
        local_subrs=[],
        global_subrs=_chain(T2_MAX, CALLGSUBR),
    )
    assert ok.get_path("A")[0] == ("moveto", 100.0, 100.0)
    bad = _font(
        glyphs={"A": _call(CALLGSUBR)},
        local_subrs=[],
        global_subrs=_chain(T2_MAX + 1, CALLGSUBR),
    )
    with pytest.raises(OSError, match=T2_MSG):
        bad.get_path("A")


@pytest.mark.parametrize(
    ("calls", "ok"),
    [(T2_MAX, True), (T2_MAX + 1, False)],
    ids=["150_calls", "151_calls"],
)
def test_type2_counts_sequential_calls_cumulatively(calls: int, ok: bool) -> None:
    # Upstream never decrements the counter, so flat sequential calls count.
    glyph = bytes([T2_SUBR_0, CALLSUBR] * calls + [ENDCHAR])
    font = _font(glyphs={"A": glyph}, local_subrs=[bytes([RETURN])])
    if ok:
        assert font.get_path("A") == []
        assert font.get_width("A") == 0.0
    else:
        with pytest.raises(OSError, match=T2_MSG):
            font.get_path("A")


@pytest.mark.parametrize(
    ("n_global", "ok"),
    [(T2_MAX // 2, True), (T2_MAX // 2 + 1, False)],
    ids=["75_plus_75", "75_plus_76"],
)
def test_type2_local_and_global_calls_share_one_counter(n_global: int, ok: bool) -> None:
    glyph = bytes(
        [T2_SUBR_0, CALLSUBR] * (T2_MAX // 2)
        + [T2_SUBR_0, CALLGSUBR] * n_global
        + [ENDCHAR]
    )
    font = _font(
        glyphs={"A": glyph}, local_subrs=[bytes([RETURN])], global_subrs=[bytes([RETURN])]
    )
    if ok:
        assert font.get_path("A") == []
    else:
        with pytest.raises(OSError, match=T2_MSG):
            font.get_path("A")


@pytest.mark.parametrize(
    ("local", "glob", "op"),
    [
        ([bytes([T2_SUBR_0, CALLSUBR])], [], CALLSUBR),
        ([bytes([T2_SUBR_0 + 1, CALLSUBR]), bytes([T2_SUBR_0, CALLSUBR])], [], CALLSUBR),
        ([], [bytes([T2_SUBR_0, CALLGSUBR])], CALLGSUBR),
        ([bytes([T2_SUBR_0, CALLGSUBR])], [bytes([T2_SUBR_0, CALLSUBR])], CALLSUBR),
    ],
    ids=["local_self", "local_mutual", "global_self", "local_global_mutual"],
)
def test_type2_recursive_subrs_raise(local: list[bytes], glob: list[bytes], op: int) -> None:
    font = _font(glyphs={"A": _call(op)}, local_subrs=local, global_subrs=glob)
    with pytest.raises(OSError, match=T2_MSG):
        font.get_path("A")
    with pytest.raises(OSError, match=T2_MSG):
        font.get_width("A")


def test_type2_counter_is_per_glyph_and_failure_is_not_cached() -> None:
    subrs = [bytes([RETURN])]
    font = _font(
        glyphs={
            "A": bytes([T2_SUBR_0, CALLSUBR] * (T2_MAX + 1) + [ENDCHAR]),
            "B": bytes([T2_SUBR_0, CALLSUBR] * T2_MAX + [ENDCHAR]),
        },
        local_subrs=subrs,
    )
    with pytest.raises(OSError):
        font.get_width("A")
    # a fresh count for the next glyph
    assert font.get_width("B") == 0.0
    # the rejected glyph keeps failing, like upstream (nothing cached)
    with pytest.raises(OSError):
        font.get_width("A")
    widths = font.get_glyph_widths()
    assert "A" not in widths
    assert widths["B"] == 0.0


def test_type2_normal_glyph_is_unaffected() -> None:
    glyph = bytes([NUMBER_100, NUMBER_100, RMOVETO, ENDCHAR])
    font = _font(glyphs={"A": glyph}, local_subrs=[])
    assert font.get_path("A")[0] == ("moveto", 100.0, 100.0)


# ---------------------------------------------------------------------------
# Type 2 inside an OpenType (OTTO) program: drawn via the fontTools glyph set
# ---------------------------------------------------------------------------


def _otf(chain_length: int) -> TrueTypeFont:
    fb = _fontbuilder({"A": _call()}, _chain(chain_length))
    fb.setupHorizontalMetrics({".notdef": (0, 0), "A": (500, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2()
    fb.setupNameTable({"familyName": "T", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    return TrueTypeFont.from_bytes(buf.getvalue())


def test_open_type_glyph_set_is_limited() -> None:
    ok = _otf(T2_MAX)
    assert PDCIDFontType2._draw_glyph(ok, 1)[0] == ("moveto", 100.0, 100.0)
    bad = _otf(T2_MAX + 1)
    with pytest.raises(OSError, match="nested more than 150 levels"):
        PDCIDFontType2._draw_glyph(bad, 1)


def test_limited_glyph_set_proxy() -> None:
    ttf = _otf(T2_MAX + 1)
    raw = ttf._tt.getGlyphSet()
    wrapped = limited_glyph_set(raw, "T")
    assert isinstance(wrapped, LimitedGlyphSet)
    assert limited_glyph_set(wrapped) is wrapped
    assert limited_glyph_set(None) is None
    assert "A" in wrapped
    assert len(wrapped) == len(raw)
    assert wrapped["A"].width == 500
    assert wrapped.get("missing") is None
    with pytest.raises(KeyError):
        wrapped["missing"]
    with pytest.raises(OSError, match=T2_MSG):
        wrapped["A"].draw(RecordingPen())


# ---------------------------------------------------------------------------
# Type 1
# ---------------------------------------------------------------------------


def _t1_chain(length: int) -> list[T1CharString]:
    subrs = [T1CharString(program=[i, "callsubr", "return"]) for i in range(1, length)]
    subrs.append(T1CharString(program=[100, 100, "rmoveto", 50, 0, "rlineto", "return"]))
    return subrs


def _t1_glyph(subrs: list[T1CharString], width: int = 500) -> T1CharString:
    return T1CharString(program=[0, width, "hsbw", 0, "callsubr", "endchar"], subrs=subrs)


T1_MSG = r"Subroutines are nested more than 106 levels deep in glyph 'a' of font T1"


def _type1_font(charstrings: dict[str, T1CharString]) -> Type1Font:
    font = Type1Font()
    font._charstrings = charstrings
    font.get_name = lambda: "T1"  # type: ignore[method-assign]
    return font


def test_type1_chain_at_limit_renders() -> None:
    font = _type1_font({"a": _t1_glyph(_t1_chain(T1_MAX))})
    assert font.get_path("a")[0] == ("moveto", 100.0, 100.0)
    assert font.get_width("a") == 500.0
    cs = Type1CharString(None, "T1", "a", _t1_glyph(_t1_chain(T1_MAX)))
    assert cs.get_path()[0] == ("moveto", 100.0, 100.0)
    assert cs.get_width() == 500.0


def test_type1_chain_over_limit_raises() -> None:
    font = _type1_font({"a": _t1_glyph(_t1_chain(T1_MAX + 1))})
    with pytest.raises(OSError, match=T1_MSG):
        font.get_path("a")
    with pytest.raises(OSError, match=T1_MSG):
        font.get_width("a")
    cs = Type1CharString(None, "T1", "a", _t1_glyph(_t1_chain(T1_MAX + 1)))
    with pytest.raises(OSError, match=T1_MSG):
        cs.get_path()
    with pytest.raises(OSError, match=T1_MSG):
        cs.get_width()
    with pytest.raises(OSError, match=T1_MSG):
        cs.render()


@pytest.mark.parametrize(
    "programs",
    [
        [[0, "callsubr"]],
        [[1, "callsubr"], [0, "callsubr"]],
    ],
    ids=["self", "mutual"],
)
def test_type1_recursive_subrs_raise(programs: list[list[object]]) -> None:
    subrs = [T1CharString(program=list(p)) for p in programs]
    font = _type1_font({"a": _t1_glyph(subrs)})
    with pytest.raises(OSError, match=T1_MSG):
        font.get_path("a")
    with pytest.raises(OSError, match=T1_MSG):
        font.get_width("a")


def test_type1_counts_depth_not_calls() -> None:
    # 300 sequential depth-1 calls are fine for Type 1.
    subrs = [T1CharString(program=[10, 0, "rlineto", "return"])]
    glyph = T1CharString(
        program=[0, 500, "hsbw", 0, 0, "rmoveto"] + [0, "callsubr"] * 300 + ["endchar"],
        subrs=subrs,
    )
    font = _type1_font({"a": glyph})
    path = font.get_path("a")
    assert len([c for c in path if c[0] == "lineto"]) == 300


def test_type1_seac_skips_a_component_over_the_limit(caplog: pytest.LogCaptureFixture) -> None:
    # Upstream Type1CharString.seac logs the component's IOException and
    # keeps the base glyph.
    base = T1CharString(
        program=[0, 500, "hsbw", 10, 10, "rmoveto", 100, 0, "rlineto", "endchar"], subrs=[]
    )
    accent = _t1_glyph(_t1_chain(T1_MAX + 1))
    composite = T1CharString(program=[0, 500, "hsbw", 0, 0, 0, 65, 194, "seac"], subrs=[])
    font = _type1_font({"A": base, "acute": accent, "Aacute": composite})
    with caplog.at_level("WARNING"):
        path = font.get_path("Aacute")
    assert path == [("moveto", 10.0, 10.0), ("lineto", 110.0, 10.0)]
    assert "invalid seac character" in caplog.text

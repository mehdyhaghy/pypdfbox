"""Hand-written tests for ``TrueTypeInterpreter``.

Covers the Java 32-bit ``int`` wrapping of the arithmetic opcodes, the
fast/slow paths of the push family, Python-specific stack handling (an
``IndexError`` from an empty stack surfaces as ``HintingException``), and an
end-to-end check of the interpreter against FreeType reference outlines for
LiberationSans-Regular, driven the way the upcoming ``GlyphHinter`` drives it.
"""

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.hinting_exception import HintingException
from pypdfbox.fontbox.ttf.true_type_interpreter import TrueTypeInterpreter
from pypdfbox.fontbox.ttf.zone import Zone

INT_MIN = -(2**31)
INT_MAX = 2**31 - 1

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "ttf"


def _interp(stack=256):
    return TrueTypeInterpreter(stack, 16, 4, 2048)


def _stack(program, stack=256):
    ctx = _interp(stack).execute_program(bytes(program), 16)
    depth = ctx.get_stack_depth()
    return [ctx.peek(depth - 1 - i) for i in range(depth)]


def _push_int(value):
    """Bytecode pushing an arbitrary 32-bit value using PUSHW, MUL and ADD."""
    hi = (value >> 16) & 0xFFFF
    lo = value & 0xFFFF
    hi_s = hi - 0x10000 if hi & 0x8000 else hi
    # hi * 65536 = MUL(MUL(hi, 64 * 64), 64 * 16) in 26.6: MUL(a, b) = a * b / 64
    prog = [0xB8, (hi_s >> 8) & 0xFF, hi_s & 0xFF]
    prog += [0xB8, 0x10, 0x00, 0x63]  # * 4096 / 64 = * 64
    prog += [0xB8, 0x10, 0x00, 0x63]  # * 64 again -> * 4096
    prog += [0xB8, 0x04, 0x00, 0x63]  # * 1024 / 64 = * 16 -> * 65536
    # add the low half as two non-negative words
    prog += [0xB8, (lo >> 9) & 0x7F, (lo >> 1) & 0xFF, 0x20, 0x60, 0x60]  # + 2 * (lo >> 1)
    prog += [0xB0, lo & 1, 0x60]
    return prog


@pytest.mark.parametrize("value", [INT_MAX, INT_MIN, -1, 123456789, -987654321])
def test_push_int_helper(value):
    assert _stack(_push_int(value)) == [value]


def test_add_sub_wrap():
    assert _stack([*_push_int(INT_MAX), 0xB0, 1, 0x60]) == [INT_MIN]
    assert _stack([*_push_int(INT_MIN), 0xB0, 1, 0x61]) == [INT_MAX]


def test_neg_and_abs_of_int_min_stay_int_min():
    assert _stack([*_push_int(INT_MIN), 0x65]) == [INT_MIN]  # NEG
    assert _stack([*_push_int(INT_MIN), 0x64]) == [INT_MIN]  # ABS
    assert _stack([0xB8, 0xFF, 0xFE, 0x64]) == [2]


def test_mul_div_floor_ceiling_opcodes():
    assert _stack([*_push_int(INT_MAX), *_push_int(INT_MAX), 0x63]) == [
        Fixed.mul(INT_MAX, INT_MAX)
    ]
    assert _stack([0xB8, 0xFF, 0x00, 0xB0, 0, 0x62]) == [0]  # DIV by zero
    assert _stack([0xB8, 0xFF, 0x9C, 0x66]) == [-128]  # FLOOR(-100)
    assert _stack([*_push_int(INT_MAX), 0x67]) == [INT_MIN]  # CEILING wraps
    assert _stack([0xB1, 3, 9, 0x8B, 0xB1, 3, 9, 0x8C]) == [9, 3]  # MAX, MIN


def test_comparisons_and_logic():
    assert _stack([0xB1, 1, 2, 0x50, 0xB1, 2, 2, 0x51, 0xB1, 1, 2, 0x52, 0xB1, 2, 2, 0x53]) == [
        1,
        1,
        0,
        1,
    ]
    assert _stack([0xB1, 2, 2, 0x54, 0xB1, 2, 2, 0x55]) == [1, 0]


def test_empty_stack_is_a_hinting_exception():
    for opcode in (0x21, 0x23, 0x60, 0x64, 0x58, 0x2B, 0x8A, 0x66, 0x68, 0x6C, 0x20, 0x10):
        with pytest.raises(HintingException, match="stack"):
            _interp().execute_program(bytes([opcode]), 16)


def test_push_family_respects_stack_capacity():
    # fast path refused, slow path pushes what fits and then overflows, as upstream does
    for program in (
        [0x40, 3, 1, 2, 3],  # NPUSHB 3
        [0x41, 3, 0, 1, 0, 2, 0, 3],  # NPUSHW 3
        [0xB2, 1, 2, 3],  # PUSHB[3]
        [0xBA, 0, 1, 0, 2, 0, 3],  # PUSHW[3]
        [0xB1, 1, 2, 0xB0, 3],  # PUSHB[1] fits, PUSHB[0] overflows
        [0xB1, 1, 2, 0xB8, 0, 3],
        [0xB1, 1, 2, 0x20],  # DUP
        [0xB1, 1, 2, 0x24],  # DEPTH
        [0xB1, 1, 2, 0x4B],  # MPPEM
        [0xB0, 1, 0x0C],  # GPV pushes two
    ):
        with pytest.raises(HintingException, match="overflow"):
            _interp(stack=2).execute_program(bytes(program), 16)
    assert _stack([0x40, 2, 7, 8], stack=2) == [7, 8]


def test_push_family_reads_past_end():
    for program in (
        [0x40],
        [0x40, 2, 1],
        [0x41, 1, 0],
        [0xB2, 1, 2],
        [0xB8, 1],
        [0xB9, 0, 1, 0],
        [0xB0],
    ):
        with pytest.raises(HintingException, match="past end"):
            _interp().execute_program(bytes(program), 16)


def test_npushw_and_pushw_are_signed():
    assert _stack([0x41, 2, 0x80, 0x00, 0x7F, 0xFF]) == [-32768, 32767]
    assert _stack([0xB9, 0xFF, 0xFF, 0x00, 0x05]) == [-1, 5]


def test_skipped_branch_with_truncated_push_is_an_error():
    # the skip scan reads NPUSHB's count byte and seeks past the operands, both bounds-checked
    with pytest.raises(HintingException):
        _interp().execute_program(bytes([0xB0, 0, 0x58, 0x40]), 16)
    with pytest.raises(HintingException):
        _interp().execute_program(bytes([0xB0, 0, 0x58, 0x41, 5, 0, 0, 0x59]), 16)


def test_idef_cannot_override_a_builtin_opcode():
    # IDEF for ADD (0x60) is recorded but the built-in handler keeps priority
    assert _stack([0xB0, 0x60, 0x89, 0xB0, 99, 0x2D, 0xB1, 2, 3, 0x60]) == [5]


def test_sds_shift_is_masked_like_java():
    # DELTAC1 with deltaShift 35: Java's 64 >> 35 shifts by 35 & 31 == 3 -> 8 per step
    interp = TrueTypeInterpreter(64, 0, 0, 2048)
    interp.set_control_values([0])
    interp.set_ppem(9, 9)
    # SDS 35 ; PUSHB arg=0x0F (ppem 9 + 0, step 15 -> +8), cvt 0, n=1 ; DELTAC1 ; RCVT 0
    ctx = interp.execute_program(bytes([0xB0, 35, 0x5F, 0xB2, 0x0F, 0, 1, 0x73, 0xB0, 0, 0x45]), 9)
    assert ctx.peek(0) == 8 * 8


def test_flip_range_clamps_bounds():
    interp = _interp()
    ctx = interp.new_context(GraphicsState())
    zone = Zone(4, 1)
    ctx.set_glyph_zone(zone)
    # FLIPRGON low=-5 high=2, then FLIPRGOFF low=1 high=99
    interp.run(ctx, BytecodeStream(bytes([0xB8, 0xFF, 0xFB, 0xB0, 2, 0x81])))
    assert zone.get_on_curve() == [True, True, True, False]
    interp.run(ctx, BytecodeStream(bytes([0xB1, 1, 99, 0x82])))
    assert zone.get_on_curve() == [True, False, False, False]


def test_jump_target_out_of_range():
    with pytest.raises(HintingException, match="seek out of range"):
        _interp().execute_program(bytes([0xB0, 50, 0x1C]), 16)
    with pytest.raises(HintingException, match="seek out of range"):
        _interp().execute_program(bytes([*_push_int(INT_MAX), 0x1C]), 16)


def test_execute_program_without_size_uses_default_state():
    interp = _interp()
    assert interp.get_saved_state() is None
    ctx = interp.execute_program(bytes([0xB0, 1, 0x56]), 16)  # ODD(1) under round-to-grid
    assert ctx.peek(0) == 0
    interp.set_ppem(16, 12)
    assert interp.get_saved_state() is not None
    assert interp.execute_program(bytes([0x4C]), 16).peek(0) == 12  # MPS


def test_prepare_font_program_resets_definitions():
    interp = _interp()
    interp.set_font_program(bytes([0xB0, 1, 0x2C, 0x2D]))
    interp.prepare_font_program()
    assert set(interp.get_functions()) == {1}
    interp.set_font_program(None)
    interp.prepare_font_program()
    assert interp.get_functions() == {}


# --- end-to-end against FreeType ---------------------------------------------------------------


def _golden(ppem):
    path = FIXTURES / "hinting" / f"LiberationSans-Regular-{ppem}.txt"
    if not path.exists():
        pytest.skip(f"golden data not present: {path}")
    glyphs = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("glyph "):
            gid = int(line.split()[1])
            xs = [int(v) for v in lines[i + 2].split()[1:]]
            ys = [int(v) for v in lines[i + 3].split()[1:]]
            glyphs[gid] = (xs, ys)
    return glyphs


@pytest.fixture(scope="module")
def liberation():
    ttlib = pytest.importorskip("fontTools.ttLib")
    path = FIXTURES / "LiberationSans-Regular.ttf"
    if not path.exists():
        pytest.skip(f"fixture font not present: {path}")
    return ttlib.TTFont(str(path))


def _hint_simple_glyph(font, interp, ppem, gid):
    """Hints one simple glyph the way GlyphHinter.hintSimple drives the interpreter."""
    upem = font["head"].unitsPerEm
    name = font.getGlyphOrder()[gid]
    glyph = font["glyf"][name]
    coords = glyph.getCoordinates(font["glyf"])[0]
    advance, lsb = font["hmtx"][name]
    n = len(coords)
    zone = Zone(n + 4, glyph.numberOfContours)
    cx, cy = zone.get_current_x(), zone.get_current_y()
    ox, oy = zone.get_original_x(), zone.get_original_y()
    ux, uy = zone.get_unscaled_x(), zone.get_unscaled_y()
    for i, (x, y) in enumerate(coords):
        ux[i], uy[i] = x, y
        ox[i] = cx[i] = Fixed.scale(x, ppem, upem)
        oy[i] = cy[i] = Fixed.scale(y, ppem, upem)
        zone.get_on_curve()[i] = bool(glyph.flags[i] & 1)
    zone.get_contour_ends()[:] = list(glyph.endPtsOfContours)
    origin = glyph.xMin - lsb
    px = [origin, origin + advance, 0, 0]
    py = [0, 0, glyph.yMax, glyph.yMax - upem]
    for i in range(4):
        k = n + i
        ux[k], uy[k] = px[i], py[i]
        ox[k], oy[k] = Fixed.scale(px[i], ppem, upem), Fixed.scale(py[i], ppem, upem)
        cx[k], cy[k] = Fixed.round(ox[k]), Fixed.round(oy[k])
    saved = interp.get_saved_state()
    gs = GraphicsState() if saved.get_instruct_control() & 2 else saved.copy()
    gs.reset_for_glyph()
    ctx = interp.new_context(gs)
    ctx.set_ppem(ppem)
    ctx.set_glyph_zone(zone)
    ctx.set_backward_compatibility((gs.get_instruct_control() & 4) == 0)
    interp.run(ctx, BytecodeStream(glyph.program.getBytecode()))
    origin_x = ox[n] if ctx.is_backward_compatibility() else cx[n]
    return [x - origin_x for x in cx[:n]], cy[:n]


@pytest.mark.parametrize("ppem", [11, 13, 16, 24])
def test_simple_glyphs_match_freetype(liberation, ppem):
    golden = _golden(ppem)
    maxp = liberation["maxp"]
    interp = TrueTypeInterpreter(
        maxp.maxStackElements,
        maxp.maxStorage,
        maxp.maxTwilightPoints,
        liberation["head"].unitsPerEm,
    )
    interp.set_font_program(bytes(liberation["fpgm"].program.getBytecode()))
    interp.set_control_value_program(bytes(liberation["prep"].program.getBytecode()))
    interp.set_control_values(list(liberation["cvt "].values))
    interp.prepare_font_program()
    interp.set_ppem(ppem, ppem)
    order = liberation.getGlyphOrder()
    checked = 0
    for gid, expected in golden.items():
        glyph = liberation["glyf"][order[gid]]
        if glyph.isComposite() or glyph.numberOfContours <= 0:
            continue  # composites need GlyphHinter's assembly (next wave)
        assert _hint_simple_glyph(liberation, interp, ppem, gid) == expected, f"gid {gid}"
        checked += 1
    assert checked > 10

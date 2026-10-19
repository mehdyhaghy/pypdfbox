"""Port of upstream ``TrueTypeInterpreterTest``: program-level tests with no font.

Hand-assembled bytecode fed through the dispatch loop. These exercise the
engine - dispatch, the push family, branching, function definition and
calling, and the BytecodeStream bounds checks - independently of any glyph.
"""

import pytest

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.hinting_exception import HintingException
from pypdfbox.fontbox.ttf.true_type_interpreter import TrueTypeInterpreter

# opcodes used to assemble test programs
PUSHB1 = 0xB0  # PUSHB[0] - push one byte
PUSHB2 = 0xB1  # PUSHB[1] - push two bytes
NPUSHW = 0x41
ADD = 0x60
SUB = 0x61
MUL = 0x63
DUP = 0x20
SWAP = 0x23
DEPTH = 0x24
ROLL = 0x8A
CINDEX = 0x25
MINDEX = 0x26
NPUSHB = 0x40
JROF = 0x79
POP = 0x21
GT = 0x52
ODD = 0x56
EVEN = 0x57
AND = 0x5A
OR = 0x5B
NOT = 0x5C
RTHG = 0x19
RDTG = 0x7D
ROFF = 0x7A
IF = 0x58
ELSE = 0x1B
EIF = 0x59
PUSHW1 = 0xB8  # PUSHW[0] - push one signed word
JMPR = 0x1C
JROT = 0x78
FDEF = 0x2C
ENDF = 0x2D
CALL = 0x2B
LOOPCALL = 0x2A
MPPEM = 0x4B
WS = 0x42
RS = 0x43
SZPS = 0x16
SCFS = 0x48
GC = 0x46
INSTCTRL = 0x8E


def _interpreter():
    return TrueTypeInterpreter(256, 16, 0, 2048)


def _p(*codes):
    """``(byte) x`` for each code, as the Java byte[] literals do."""
    return bytes(c & 0xFF for c in codes)


def _run_top(program):
    return _interpreter().execute_program(program, 16).peek(0)


def _run_stack(program):
    """Runs the program and returns the whole stack, bottom to top."""
    ctx = _interpreter().execute_program(program, 16)
    depth = ctx.get_stack_depth()
    return [ctx.peek(depth - 1 - i) for i in range(depth)]


def test_push_and_add():
    assert _run_top(_p(PUSHB2, 2, 3, ADD)) == 5


def test_npushw_signed():
    assert _run_top(_p(NPUSHW, 1, 0xFF, 0xFF)) == -1


def test_arithmetic():
    assert _run_top(_p(PUSHB2, 10, 3, SUB)) == 7
    # 2.0 * 3.0 in F26Dot6: push 128 and 192 via NPUSHW
    assert _run_top(_p(NPUSHW, 2, 0, 128, 0, 192, MUL)) == Fixed.from_int(6)


def test_stack_ops():
    # DUP: push 7, dup, add -> 14
    assert _run_top(_p(PUSHB1, 7, DUP, ADD)) == 14
    # SWAP then SUB: push 3,10 swap -> 10,3 ; SUB pops b=3,a=10 -> 7
    assert _run_top(_p(PUSHB2, 3, 10, SWAP, SUB)) == 7
    # DEPTH after pushing three values -> 3
    assert _run_top(_p(PUSHB2, 1, 2, PUSHB1, 9, DEPTH)) == 3
    # ROLL: 1 2 3 -> 2 3 1, top is 1
    assert _run_top(_p(PUSHB2, 1, 2, PUSHB1, 3, ROLL)) == 1


def test_roll_full_permutation():
    # [1 2 3] ROLL -> [2 3 1]; SUB -> 3 - 1 = 2; SUB -> 2 - 2 = 0
    assert _run_top(_p(PUSHB2, 1, 2, PUSHB1, 3, ROLL, SUB, SUB)) == 0
    # [5 7 9] ROLL -> [7 9 5]; SUB -> 9 - 5 = 4; SUB -> 7 - 4 = 3
    assert _run_top(_p(PUSHB2, 5, 7, PUSHB1, 9, ROLL, SUB, SUB)) == 3


def test_odd_even_use_round_state():
    # ODD/EVEN round the operand with the current round state before testing the pixel's parity
    # (spec, and FreeType's Ins_ODD/Ins_EVEN)
    assert _run_top(_p(PUSHB1, 90, ODD)) == 1
    assert _run_top(_p(PUSHB1, 90, EVEN)) == 0
    assert _run_top(_p(PUSHB1, 102, ODD)) == 0
    assert _run_top(_p(PUSHB1, 102, EVEN)) == 1
    assert _run_top(_p(RDTG, PUSHB1, 102, ODD)) == 1
    # round-to-half-grid: 1.4 px -> 1.5 px, which is neither an odd nor an even pixel
    assert _run_top(_p(RTHG, PUSHB1, 90, ODD)) == 0
    assert _run_top(_p(RTHG, PUSHB1, 90, EVEN)) == 0
    # round off: the value is tested as-is; 64 is odd, 128 even, 90 neither
    assert _run_top(_p(ROFF, PUSHB1, 64, ODD)) == 1
    assert _run_top(_p(ROFF, PUSHB1, 128, EVEN)) == 1
    assert _run_top(_p(ROFF, PUSHB1, 90, ODD)) == 0
    assert _run_top(_p(ROFF, PUSHB1, 90, EVEN)) == 0


def test_and_or_not():
    assert _run_top(_p(PUSHB2, 3, 64, AND)) == 1
    assert _run_top(_p(PUSHB2, 3, 0, AND)) == 0
    assert _run_top(_p(PUSHB2, 0, 5, OR)) == 1
    assert _run_top(_p(PUSHB2, 0, 0, OR)) == 0
    assert _run_top(_p(PUSHB1, 0, NOT)) == 1
    assert _run_top(_p(PUSHB1, 9, NOT)) == 0


def test_if_else_true_branch():
    assert _run_top(_p(PUSHB1, 1, IF, PUSHB1, 10, ELSE, PUSHB1, 20, EIF)) == 10


def test_if_else_false_branch():
    assert _run_top(_p(PUSHB1, 0, IF, PUSHB1, 10, ELSE, PUSHB1, 20, EIF)) == 20


def test_nested_if():
    # outer true, inner (5>3) true -> 99
    program = _p(
        PUSHB1, 1, IF,
        PUSHB2, 5, 3, GT, IF,
        PUSHB1, 99,
        ELSE,
        PUSHB1, 1,
        EIF,
        ELSE,
        PUSHB1, 7,
        EIF,
    )  # fmt: skip
    assert _run_top(program) == 99


def test_jmpr():
    # layout: [0]PUSHB1 [1]3 [2]JMPR [3]PUSHB1 [4]7(skipped) [5]PUSHB1 [6]42
    ctx = _interpreter().execute_program(_p(PUSHB1, 3, JMPR, PUSHB1, 7, PUSHB1, 42), 16)
    assert ctx.peek(0) == 42
    assert ctx.get_stack_depth() == 1  # the skipped push never ran


def test_function_def_and_call():
    # define function 5 = "double the top" (DUP ADD); call it on 21 -> 42
    interp = _interpreter()
    interp.set_font_program(_p(PUSHB1, 5, FDEF, DUP, ADD, ENDF))
    interp.prepare_font_program()
    assert len(interp.get_functions()) == 1

    ctx = interp.execute_program(_p(PUSHB1, 21, PUSHB1, 5, CALL), 16)
    assert ctx.peek(0) == 42


def test_loop_call():
    # function 1 = "add 1"; LOOPCALL it 3 times starting from 0 -> 3
    interp = _interpreter()
    interp.set_font_program(_p(PUSHB1, 1, FDEF, PUSHB1, 1, ADD, ENDF))
    interp.prepare_font_program()
    # stack: value=0, count=3, fn=1 ; LOOPCALL pops fn then count
    ctx = interp.execute_program(_p(PUSHB1, 0, PUSHB2, 3, 1, LOOPCALL), 16)
    assert ctx.peek(0) == 3


def test_call_depth_limit_trips():
    # function 0 calls itself unconditionally -> must trip the depth cap, not a RecursionError
    interp = _interpreter()
    interp.set_font_program(_p(PUSHB1, 0, FDEF, PUSHB1, 0, CALL, ENDF))
    interp.prepare_font_program()
    with pytest.raises(HintingException) as ex:
        interp.execute_program(_p(PUSHB1, 0, CALL), 16)
    assert "call depth" in ex.value.get_message()


def test_idef_defines_opcode():
    # IDEF binds reserved opcode 0x83 to "push 42"; invoking 0x83 then runs that body.
    ctx = _interpreter().execute_program(_p(PUSHB1, 0x83, 0x89, PUSHB1, 42, ENDF, 0x83), 16)
    assert ctx.peek(0) == 42


def test_undefined_function_throws():
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(PUSHB1, 9, CALL), 16)


def test_mppem_reflects_ppem():
    ctx = _interpreter().execute_program(_p(MPPEM), 19)
    assert ctx.peek(0) == 19


def test_unsupported_opcode_throws():
    # 0x28 is a reserved/unused opcode; unimplemented opcodes must throw, not no-op
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(0x28), 16)


def test_control_value_scaling_through_prep():
    # raw cvt [2048] at 16 ppem, unitsPerEm 2048 -> scaled to 16px (1024 in F26Dot6)
    interp = _interpreter()
    interp.set_control_values([2048])
    interp.set_ppem(16, 16)
    ctx = interp.execute_program(_p(PUSHB1, 0, 0x45), 16)  # RCVT 0
    assert ctx.peek(0) == Fixed.from_int(16)


def test_backward_jump_is_bounded():
    # PUSHW -3 ; JMPR jumps back onto its own push; it must hit the execution budget and throw
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(PUSHW1, 0xFF, 0xFD, JMPR), 16)


def test_backward_jump_within_budget_completes():
    # counter = 60; loop { counter -= 1; if (counter != 0) jump back } -> 59 backward jumps
    # [0]PUSHW1 60 [3]PUSHB1 1 [5]SUB [6]DUP [7]PUSHW1 -8 [10]SWAP [11]JROT
    program = _p(PUSHW1, 0, 60, PUSHB1, 1, SUB, DUP, PUSHW1, 0xFF, 0xF8, SWAP, JROT)
    ctx = _interpreter().execute_program(program, 16)
    assert ctx.peek(0) == 0
    assert ctx.get_stack_depth() == 1


def test_prep_loop_call_budget_is_sized_from_the_control_values():
    # FreeType's TT_RunIns gives a program without glyph points (fpgm/prep) 300 + 22 * cvtSize
    # LOOPCALL iterations; the glyph formula would allow only 100 here.
    interp = _interpreter()
    interp.set_font_program(_p(PUSHB1, 1, FDEF, PUSHB1, 1, ADD, ENDF))
    interp.prepare_font_program()
    interp.set_control_value_program(
        _p(PUSHB1, 0, PUSHB1, 240, PUSHB1, 1, LOOPCALL, PUSHB1, 7, SWAP, WS)
    )
    interp.set_ppem(16, 16)
    assert interp.execute_program(_p(PUSHB1, 7, RS), 16).peek(0) == 240


def test_loop_call_count_is_bounded():
    # the whole loop is charged against the budget up front, so an absurd count fails before a
    # single iteration runs
    interp = _interpreter()
    interp.set_font_program(_p(PUSHB1, 1, FDEF, PUSHB1, 1, ADD, ENDF))
    interp.prepare_font_program()
    with pytest.raises(HintingException):
        interp.execute_program(_p(PUSHB1, 0, PUSHW1, 0x7F, 0xFF, PUSHB1, 1, LOOPCALL), 16)


def test_non_positive_loop_call_count_runs_nothing():
    interp = _interpreter()
    interp.set_font_program(_p(PUSHB1, 1, FDEF, PUSHB1, 1, ADD, ENDF))
    interp.prepare_font_program()
    # stack: value=7, count=-1, fn=1 -> the function never runs, 7 is left untouched
    ctx = interp.execute_program(_p(PUSHB1, 7, PUSHW1, 0xFF, 0xFF, PUSHB1, 1, LOOPCALL), 16)
    assert ctx.peek(0) == 7
    assert ctx.get_stack_depth() == 1


def test_storage_persists_from_prep_into_glyph_program():
    interp = _interpreter()
    interp.set_control_value_program(_p(PUSHB2, 5, 42, WS))  # storage[5] = 42
    interp.set_ppem(16, 16)
    ctx = interp.execute_program(_p(PUSHB1, 5, RS), 16)
    assert ctx.peek(0) == 42


def _instruct_control_after_prep(*value_selector_pairs):
    """Runs INSTCTRL once per (value, selector) pair in prep and returns the saved flags."""
    prep = []
    for i in range(0, len(value_selector_pairs), 2):
        prep += [PUSHB2, value_selector_pairs[i], value_selector_pairs[i + 1], INSTCTRL]
    interp = _interpreter()
    interp.set_control_value_program(_p(*prep))
    interp.set_ppem(16, 16)
    return interp.get_saved_state().get_instruct_control()


def test_instctrl_in_prep_sets_and_clears_single_bits():
    assert _instruct_control_after_prep(1, 1) == 1
    assert _instruct_control_after_prep(1, 1, 2, 2) == 3
    assert _instruct_control_after_prep(1, 1, 2, 2, 4, 3, 0, 1) == 6
    assert _instruct_control_after_prep(1, 4) == 0  # selector out of range
    assert _instruct_control_after_prep(1, 2) == 0  # value is not the selector's bit
    assert _instruct_control_after_prep(1, 0) == 0  # selector out of range


def test_instctrl_outside_prep_leaves_flags_alone():
    interp = _interpreter()
    interp.set_ppem(16, 16)
    ctx = interp.execute_program(_p(PUSHB2, 1, 1, INSTCTRL), 16)
    assert ctx.get_graphics_state().get_instruct_control() == 0

    ctx = interp.new_context(interp.get_saved_state().copy())
    ctx.set_backward_compatibility(True)
    interp.run(ctx, BytecodeStream(_p(PUSHB2, 4, 3, INSTCTRL)))
    assert not ctx.is_backward_compatibility()
    interp.run(ctx, BytecodeStream(_p(PUSHB2, 0, 3, INSTCTRL)))
    assert ctx.is_backward_compatibility()
    assert ctx.get_graphics_state().get_instruct_control() == 0


def test_twilight_points_persist_from_prep():
    interp = TrueTypeInterpreter(256, 16, 4, 2048)
    # prep: aim every zone pointer at the twilight zone, then set point 1's x to 128
    interp.set_control_value_program(_p(PUSHB1, 0, SZPS, PUSHB2, 1, 128, SCFS))
    interp.set_ppem(16, 16)
    ctx = interp.execute_program(_p(PUSHB1, 0, SZPS, PUSHB1, 1, GC), 16)
    assert ctx.peek(0) == 128


def test_storage_is_cleared_on_ppem_change():
    interp = _interpreter()
    interp.set_ppem(16, 16)
    interp.execute_program(_p(PUSHB2, 5, 42, WS), 16)
    assert interp.execute_program(_p(PUSHB1, 5, RS), 16).peek(0) == 42

    interp.set_ppem(24, 24)
    assert interp.execute_program(_p(PUSHB1, 5, RS), 24).peek(0) == 0


def test_mindex():
    # stack bottom->top: 10 20 30 40 50
    five = [NPUSHB, 5, 10, 20, 30, 40, 50]
    assert _run_stack(_p(*five, PUSHB1, 1, MINDEX)) == [10, 20, 30, 40, 50]
    assert _run_stack(_p(*five, PUSHB1, 2, MINDEX)) == [10, 20, 30, 50, 40]
    assert _run_stack(_p(*five, PUSHB1, 3, MINDEX)) == [10, 20, 40, 50, 30]
    assert _run_stack(_p(*five, PUSHB1, 5, MINDEX)) == [20, 30, 40, 50, 10]
    # k = 2 is SWAP and k = 3 is ROLL
    assert _run_stack(_p(*five, PUSHB1, 2, MINDEX)) == _run_stack(_p(*five, SWAP))
    assert _run_stack(_p(*five, PUSHB1, 3, MINDEX)) == _run_stack(_p(*five, ROLL))
    # out of range: k is consumed, the rest of the stack is untouched (FreeType, non-pedantic)
    assert _run_stack(_p(*five, PUSHB1, 6, MINDEX)) == [10, 20, 30, 40, 50]
    assert _run_stack(_p(*five, PUSHB1, 0, MINDEX)) == [10, 20, 30, 40, 50]


def test_cindex():
    three = [PUSHB2, 10, 20, PUSHB1, 30]
    assert _run_stack(_p(*three, PUSHB1, 1, CINDEX)) == [10, 20, 30, 30]
    assert _run_stack(_p(*three, PUSHB1, 3, CINDEX)) == [10, 20, 30, 10]
    assert _run_stack(_p(*three, PUSHB1, 4, CINDEX)) == [10, 20, 30]


def test_jumps_are_relative_to_the_jump_opcode():
    #  0: PUSHB1 4   2: JMPR   3: PUSHB1 99   5: POP   6: PUSHB1 7
    assert _run_stack(_p(PUSHB1, 4, JMPR, PUSHB1, 99, POP, PUSHB1, 7)) == [7]
    # countdown: JROT at 10 must land on 2: offset -8
    assert _run_stack(
        _p(PUSHB1, 3, PUSHB1, 1, SUB, DUP, PUSHW1, 0xFF, 0xF8, SWAP, JROT)
    ) == [0]
    # JROF: jumps when the condition is false
    assert _run_stack(_p(PUSHB2, 4, 0, JROF, PUSHB1, 99, POP, PUSHB1, 8)) == [8]
    # with a true condition JROF falls through
    assert _run_stack(_p(PUSHB2, 4, 1, JROF, PUSHB1, 99, PUSHB1, 8)) == [99, 8]


def test_nested_if_else_with_opcode_bytes_as_push_data():
    # the skipped branch contains PUSHB operands equal to the IF, ELSE and EIF opcode bytes, and a
    # nested IF/ELSE/EIF
    program = _p(
        PUSHB1, 0, IF,  # false: skip to ELSE
        PUSHB1, EIF,  # data byte 0x59 must not end the skip
        PUSHB1, 1, IF, PUSHB1, ELSE, ELSE, PUSHB1, IF, EIF,  # nested, with data 0x1B / 0x58
        PUSHB1, 99,
        ELSE,
        PUSHB1, 1, IF, PUSHB1, 5, ELSE, PUSHB1, 6, EIF,  # nested true: 5
        PUSHB1, 0, IF, PUSHB1, 7, ELSE, PUSHB1, 8, EIF,  # nested false: 8
        EIF,
        PUSHB1, 9,
    )  # fmt: skip
    assert _run_stack(program) == [5, 8, 9]

    # and a true outer branch skips the else-branch, which itself contains nested IFs and data
    program2 = _p(
        PUSHB1, 1, IF,
        PUSHB1, 1,
        ELSE,
        PUSHB1, EIF, PUSHB1, 0, IF, PUSHB1, IF, ELSE, PUSHB1, ELSE, EIF, PUSHB1, 99,
        EIF,
        PUSHB1, 2,
    )  # fmt: skip
    assert _run_stack(program2) == [1, 2]


def test_function_bodies_nested_calls_and_returns():
    # fn 0: doubles the top (DUP ADD), but contains an IF whose skipped branch holds ENDF as data
    # fn 1: calls fn 0 twice, then pushes 100 - the push after the inner calls proves the inner
    #       ENDF did not return from fn 1
    program = _p(
        PUSHB1, 0, FDEF,
        PUSHB1, 0, IF, PUSHB1, ENDF, PUSHB1, ENDF, ELSE, DUP, ADD, EIF,
        ENDF,
        PUSHB1, 1, FDEF,
        PUSHB1, 0, CALL, PUSHB1, 0, CALL, PUSHB1, 100,
        ENDF,
        PUSHB1, 3, PUSHB1, 1, CALL,
    )  # fmt: skip
    assert _run_stack(program) == [12, 100]

    # fn 2: recursive countdown: if top != 0 { push 1, SUB, call 2 } ; leaves 0
    recursive = _p(
        PUSHB1, 2, FDEF,
        DUP, IF, PUSHB1, 1, SUB, PUSHB1, 2, CALL, EIF,
        ENDF,
        PUSHB1, 5, PUSHB1, 2, CALL, PUSHB1, 42,
    )  # fmt: skip
    assert _run_stack(recursive) == [0, 42]


def test_endf_outside_function_is_an_error():
    with pytest.raises(HintingException):
        _run_stack(_p(PUSHB1, 1, ENDF))


def test_jump_out_of_function_body_is_an_error():
    # fn 0 body: PUSHB1 20 JMPR -> would land far past ENDF
    program = _p(PUSHB1, 0, FDEF, PUSHB1, 20, JMPR, ENDF, PUSHB1, 0, CALL, PUSHB1, 1)
    with pytest.raises(HintingException):
        _run_stack(program)
    # a jump to the ENDF itself is fine (offset 3 from JMPR at 5 lands on ENDF at 8)
    ok = _p(PUSHB1, 0, FDEF, PUSHB1, 3, JMPR, PUSHB1, 99, ENDF, PUSHB1, 0, CALL, PUSHB1, 1)
    assert _run_stack(ok) == [1]


def test_get_info_reports_a_grayscale_v40_rasterizer():
    # selector: version (1), grayscale (32), subpixel (64), ClearType (1024), positioned (2048),
    # grayscale ClearType (4096)
    selector = 1 | 32 | 64 | 1024 | 2048 | 4096
    info = _run_top(_p(PUSHW1, selector >> 8, selector, 0x88))
    assert info == 40 | 1 << 13 | 1 << 17 | 1 << 18 | 1 << 19


def test_unterminated_blocks_are_hinting_exceptions():
    # false IF skipping to an ELSE/EIF that never comes
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(PUSHB1, 0, IF, PUSHB1, 1), 16)
    # true IF reaching an ELSE that skips to an EIF that never comes
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(PUSHB1, 1, IF, ELSE, PUSHB1, 1), 16)
    # FDEF without ENDF
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(PUSHB1, 0, FDEF, PUSHB1, 1), 16)


def test_storage_and_control_value_indices_are_bounded():
    # the interpreter has 16 storage slots and no control values
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(PUSHB1, 99, RS), 16)
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(PUSHB2, 99, 1, WS), 16)
    with pytest.raises(HintingException):
        _interpreter().execute_program(_p(PUSHB2, 99, 1, 0x44), 16)  # WCVTP


def test_function_body_cannot_read_operands_past_endf():
    # the body is PUSHB[0] 2, JMPR, PUSHB[0] 0xB1, ENDF: the jump lands on the operand byte 0xB1,
    # which executes as PUSHB[1] and would read the ENDF and the caller's next byte as operands
    program = _p(PUSHB1, 0, FDEF, PUSHB1, 2, JMPR, PUSHB1, 0xB1, ENDF, PUSHB1, 0, CALL)
    with pytest.raises(HintingException):
        _interpreter().execute_program(program, 16)


def test_nested_function_definition_is_an_error():
    with pytest.raises(HintingException):
        _run_stack(_p(PUSHB1, 0, FDEF, PUSHB1, 1, FDEF, ENDF, ENDF))

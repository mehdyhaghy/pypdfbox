"""Hand-written tests for ``ExecutionTracer``: mnemonics and the FreeType-like trace format."""

import io

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.execution_tracer import ExecutionTracer
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.true_type_interpreter import TrueTypeInterpreter
from pypdfbox.fontbox.ttf.zone import Zone


def test_mnemonics():
    assert ExecutionTracer.mnemonic(0x00) == "SVTCA[y]"
    assert ExecutionTracer.mnemonic(0xB0) == "PUSHB[1]"
    assert ExecutionTracer.mnemonic(0xBF) == "PUSHW[8]"
    assert ExecutionTracer.mnemonic(0xDF) == "MDRP[1f]"
    assert ExecutionTracer.mnemonic(0xE4) == "MIRP[4]"
    assert ExecutionTracer.mnemonic(0x6A) == "ROUND[2]"
    assert ExecutionTracer.mnemonic(0x28) == "INS_28"
    assert ExecutionTracer.mnemonic(0x183) == "INS_83"  # masked to a byte


def test_trace_lines_show_pc_mnemonic_and_stack_top_first():
    out = io.StringIO()
    interp = TrueTypeInterpreter(32, 0, 0, 1000)
    interp.set_tracer(ExecutionTracer(out))
    interp.execute_program(bytes([0xB1, 2, 3, 0x60]), 12)
    lines = out.getvalue().splitlines()
    assert lines == [
        "000000  PUSHB[2]    #",
        "000003  ADD         # 3 2",
    ]
    interp.set_tracer(None)
    interp.execute_program(bytes([0xB0, 1]), 12)
    assert len(out.getvalue().splitlines()) == 2


def test_trace_point_and_window():
    out = io.StringIO()
    interp = TrueTypeInterpreter(32, 0, 0, 1000)
    interp.set_tracer(ExecutionTracer(out, 1))
    ctx = interp.new_context(GraphicsState())
    zone = Zone(2, 1)
    zone.get_current_x()[1] = 70
    zone.get_current_y()[1] = -5
    ctx.set_glyph_zone(zone)
    interp.run(ctx, BytecodeStream(bytes([0x40, 10, *range(10), 0x21])))
    last = out.getvalue().splitlines()[-1]
    assert last.startswith("000012  POP         P1=(70,-5) #")
    # at most eight operands, top of stack first
    assert last.endswith("# 9 8 7 6 5 4 3 2")


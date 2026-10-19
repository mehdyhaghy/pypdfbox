"""Hand-written tests for ``ExecutionContext``: stack bounds, zones, budget and int wrapping."""

import pytest

from pypdfbox.fontbox.ttf.execution_context import ExecutionContext
from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.hinting_exception import HintingException
from pypdfbox.fontbox.ttf.zone import Zone

INT_MIN = -(2**31)
INT_MAX = 2**31 - 1


def _ctx(capacity=4, cvt=None):
    return ExecutionContext(None, GraphicsState(), capacity, [0] * 4, cvt, Zone(3, 0))


def test_stack_bounds():
    ctx = _ctx(capacity=2)
    ctx.push(1)
    ctx.push(2)
    with pytest.raises(HintingException, match="overflow"):
        ctx.push(3)
    assert ctx.peek(0) == 2
    assert ctx.peek(1) == 1
    with pytest.raises(HintingException):
        ctx.peek(2)
    with pytest.raises(HintingException):
        ctx.peek(-1)
    assert ctx.pop() == 2
    ctx.clear_stack()
    assert ctx.get_stack_depth() == 0
    with pytest.raises(HintingException, match="underflow"):
        ctx.pop()


def test_zero_capacity_still_holds_one_value():
    ctx = _ctx(capacity=0)
    ctx.push(9)
    with pytest.raises(HintingException):
        ctx.push(9)


def test_get_zone():
    ctx = _ctx()
    assert ctx.get_zone(0) is ctx.get_twilight_zone()
    with pytest.raises(HintingException, match="not loaded"):
        ctx.get_zone(1)
    glyph = Zone(1, 1)
    ctx.set_glyph_zone(glyph)
    assert ctx.get_zone(1) is glyph
    with pytest.raises(HintingException, match="invalid zone pointer"):
        ctx.get_zone(2)
    with pytest.raises(HintingException):
        ctx.get_zone(-1)


def test_execution_budget():
    assert _ctx(cvt=[0] * 10).get_execution_budget() == 300 + 22 * 10
    ctx = _ctx(cvt=[0] * 1000)
    ctx.set_glyph_zone(Zone(20, 1))
    assert ctx.get_execution_budget() == max(50, 200) + max(50, 100)
    ctx.count_loop_calls(300)
    with pytest.raises(HintingException, match="LOOPCALL"):
        ctx.count_loop_calls(1)


def test_negative_jump_budget_is_computed_once():
    ctx = _ctx(cvt=[])
    for _ in range(300):
        ctx.count_negative_jump()
    with pytest.raises(HintingException, match="backward jumps"):
        ctx.count_negative_jump()


def test_check_point_rejects_negative_indices():
    # Python lists accept negative indices; the bytecode must never reach them
    zone = Zone(2, 0)
    with pytest.raises(HintingException):
        ExecutionContext.check_point(zone, -1)
    ctx = _ctx()
    with pytest.raises(HintingException):
        ctx.move_point(zone, -1, 64)
    with pytest.raises(HintingException):
        ctx.projected_distance(zone, 0, zone, -2)


def test_move_point_wraps_coordinates_like_java():
    ctx = _ctx()
    zone = Zone(1, 0)
    zone.get_current_x()[0] = INT_MAX
    ctx.move_point(zone, 0, 1)
    assert zone.get_current_x()[0] == INT_MIN
    # the distance argument is a Java int too
    zone.get_current_x()[0] = 0
    ctx.move_point(zone, 0, INT_MAX + 1)
    assert zone.get_current_x()[0] == INT_MIN


def test_move_point_general_vector_uses_mul_div():
    ctx = _ctx()
    gs = ctx.get_graphics_state()
    gs.get_freedom_vector().set(0x2D41, 0x2D41)  # 45 degrees
    zone = Zone(1, 0)
    ctx.move_point(zone, 0, 64)
    f_dot_p = 0x2D41  # fv.x * pv.x >> 14 with pv = x axis
    assert zone.get_current_x()[0] == Fixed.mul_div(64, 0x2D41, f_dot_p)
    assert zone.get_current_y()[0] == Fixed.mul_div(64, 0x2D41, f_dot_p)
    assert zone.get_touched_x()[0] and zone.get_touched_y()[0]


def test_nearly_perpendicular_vectors_fall_back_to_one():
    ctx = _ctx()
    gs = ctx.get_graphics_state()
    gs.get_freedom_vector().set(0x3FF, 0x3FFF)  # fv . pv = 0x3FF < 0x400
    zone = Zone(1, 0)
    ctx.move_point(zone, 0, 64)
    assert zone.get_current_x()[0] == Fixed.mul_div(64, 0x3FF, 0x4000)
    assert zone.get_current_y()[0] == Fixed.mul_div(64, 0x3FFF, 0x4000)


def test_projection_wraps():
    assert ExecutionContext.dot14(INT_MAX, INT_MAX, 0x4000, 0x4000) == -2
    ctx = _ctx()
    zone = Zone(2, 0)
    zone.get_current_x()[0] = INT_MAX
    zone.get_current_x()[1] = INT_MIN
    # MIN - MAX wraps to 1 before projection, as the Java int difference does
    assert ctx.projected_distance(zone, 1, zone, 0) == 1


def test_move_original_touches_nothing():
    ctx = _ctx()
    zone = Zone(1, 0)
    ctx.set_backward_compatibility(True)
    ctx.move_original(zone, 0, 64)
    assert zone.get_original_x()[0] == 64
    assert not zone.get_touched_x()[0]


def test_code_range_and_flags():
    ctx = _ctx()
    assert ctx.get_code_range() is ExecutionContext.CodeRange.GLYPH
    ctx.set_code_range(ExecutionContext.CodeRange.FONT)
    assert ctx.get_code_range() is ExecutionContext.CodeRange.FONT
    assert not ctx.is_iup_done()
    ctx.set_iupx_called()
    assert not ctx.is_iup_done()
    ctx.set_iupy_called()
    assert ctx.is_iup_done()
    ctx.set_composite(True)
    assert ctx.is_composite()
    ctx.enter_call()
    assert ctx.get_call_depth() == 1
    ctx.leave_call()
    assert ctx.get_call_depth() == 0
    assert ctx.get_interpreter() is None
    assert ctx.get_storage() == [0] * 4
    assert ctx.get_control_values() == []

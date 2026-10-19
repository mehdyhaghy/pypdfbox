"""Port of upstream ``BackwardCompatibilityMoveTest``.

Pins the v40 "backward compatibility" movement rules in
``ExecutionContext.move_point``, a transcription of FreeType's ``Direct_Move``
under ``TT_SUPPORT_SUBPIXEL_HINTING_MINIMAL``: with the flag off,
``move_point`` is the plain spec move on both axes; with the flag on, x moves
are suppressed (the point is still marked touched, so IUP treats it as a
reference) and y moves are allowed until IUP has run on both axes, after which
the glyph is frozen.
"""

import math

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.true_type_interpreter import TrueTypeInterpreter
from pypdfbox.fontbox.ttf.zone import Zone

MOVE = 100  # 1.56 px


def _context(backward_compatibility):
    interp = TrueTypeInterpreter(32, 8, 0, 1000)
    ctx = interp.new_context(GraphicsState())
    zone = Zone(2, 1)
    zone.get_contour_ends()[0] = 1
    ctx.set_glyph_zone(zone)
    ctx.set_backward_compatibility(backward_compatibility)
    return ctx


def _freedom_y(ctx):
    ctx.get_graphics_state().get_freedom_vector().set(0, Fixed.ONE_F2DOT14)
    ctx.get_graphics_state().get_projection_vector().set(0, Fixed.ONE_F2DOT14)


def test_flag_off_is_the_plain_move():
    ctx = _context(False)
    zone = ctx.get_glyph_zone()
    ctx.move_point(zone, 0, MOVE)
    assert zone.get_current_x()[0] == MOVE
    assert zone.get_touched_x()[0]
    assert not zone.get_touched_y()[0]

    _freedom_y(ctx)
    ctx.move_point(zone, 1, MOVE)
    assert zone.get_current_y()[1] == MOVE
    assert zone.get_touched_y()[1]

    # IUP on both axes does not freeze anything when the flag is off
    ctx.set_iupx_called()
    ctx.set_iupy_called()
    ctx.move_point(zone, 1, MOVE)
    assert zone.get_current_y()[1] == 2 * MOVE


def test_flag_on_suppresses_x_but_still_touches():
    ctx = _context(True)
    zone = ctx.get_glyph_zone()
    ctx.move_point(zone, 0, MOVE)
    assert zone.get_current_x()[0] == 0, "x must not be grid-fit under backward compatibility"
    assert zone.get_touched_x()[0], "the point still counts as touched for IUP"


def test_flag_on_allows_y_until_iup_has_run_on_both_axes():
    ctx = _context(True)
    zone = ctx.get_glyph_zone()
    _freedom_y(ctx)

    ctx.move_point(zone, 0, MOVE)
    assert zone.get_current_y()[0] == MOVE, "y moves are allowed before IUP"

    ctx.set_iupx_called()  # only one axis so far: still allowed
    ctx.move_point(zone, 0, MOVE)
    assert zone.get_current_y()[0] == 2 * MOVE

    ctx.set_iupy_called()  # both axes: frozen
    ctx.move_point(zone, 0, MOVE)
    assert zone.get_current_y()[0] == 2 * MOVE, "y is frozen once IUP ran on both axes"
    assert zone.get_touched_y()[0]


def test_diagonal_freedom_vector_is_gated_per_axis():
    # a diagonal freedom vector is gated per axis: its x part is dropped, its y part applied
    ctx = _context(True)
    zone = ctx.get_glyph_zone()
    d = math.floor(Fixed.ONE_F2DOT14 / math.sqrt(2) + 0.5)
    ctx.get_graphics_state().get_freedom_vector().set(d, d)
    ctx.get_graphics_state().get_projection_vector().set(d, d)
    ctx.move_point(zone, 0, MOVE)
    assert zone.get_current_x()[0] == 0
    assert zone.get_current_y()[0] > 0
    assert zone.get_touched_x()[0]
    assert zone.get_touched_y()[0]


def test_shpix_is_gated_like_deltap():
    # SHPIX under backward compatibility is gated like DELTAP (FreeType Ins_SHPIX): a glyph-zone
    # point moves in y only if it was already touched in y and IUP has not run; twilight points
    # always move. With the flag off SHPIX is unconditional.
    interp = TrueTypeInterpreter(32, 8, 4, 1000)
    shpix_point0 = bytes([0x00, 0xB1, 0, 100, 0x38])  # SVTCA[0] y ; PUSHB[1] 0 100 ; SHPIX

    # flag off: moves
    ctx = interp.new_context(GraphicsState())
    zone = Zone(2, 1)
    zone.get_contour_ends()[0] = 1
    ctx.set_glyph_zone(zone)
    interp.run(ctx, BytecodeStream(shpix_point0))
    assert zone.get_current_y()[0] == 100

    # flag on, point untouched: blocked
    ctx = interp.new_context(GraphicsState())
    zone = Zone(2, 1)
    zone.get_contour_ends()[0] = 1
    ctx.set_glyph_zone(zone)
    ctx.set_backward_compatibility(True)
    interp.run(ctx, BytecodeStream(shpix_point0))
    assert zone.get_current_y()[0] == 0, "untouched point must not be moved by SHPIX"

    # flag on, point touched in y: moves
    zone.get_touched_y()[0] = True
    interp.run(ctx, BytecodeStream(shpix_point0))
    assert zone.get_current_y()[0] == 100

    # flag on, after IUP on both axes: blocked even though touched
    ctx.set_iupx_called()
    ctx.set_iupy_called()
    interp.run(ctx, BytecodeStream(shpix_point0))
    assert zone.get_current_y()[0] == 100

    # flag on, twilight zone: always moves (SZP2 0 first)
    ctx = interp.new_context(GraphicsState())
    ctx.set_glyph_zone(zone)
    ctx.set_backward_compatibility(True)
    twilight = bytes([0x00, 0xB0, 0, 0x15, 0xB1, 1, 100, 0x38])
    interp.run(ctx, BytecodeStream(twilight))
    assert ctx.get_twilight_zone().get_current_y()[1] == 100

"""Port of upstream ``PointOpsTest``: the point-moving opcodes.

Each test builds a glyph zone, runs a short program through the interpreter,
and asserts the resulting coordinates. Coordinates are in F26Dot6 (64 per
pixel).
"""

import pytest

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.execution_context import ExecutionContext
from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.hinting_exception import HintingException
from pypdfbox.fontbox.ttf.true_type_interpreter import TrueTypeInterpreter
from pypdfbox.fontbox.ttf.zone import Zone


def _interpreter():
    # 16ppem at 1024 units per em is a scale of exactly 1 (16 * 64 / 1024), so the synthetic
    # zones' unscaled coordinates can equal their device coordinates; MDRP and IP measure the
    # former.
    return TrueTypeInterpreter(256, 16, 16, 1024)


def _line_zone(*xs):
    """Builds a single-contour glyph zone with the given x coordinates (original == current)."""
    zone = Zone(len(xs), 1)
    for i, x in enumerate(xs):
        zone.get_original_x()[i] = x
        zone.get_current_x()[i] = x
        # these synthetic tests work directly in device units, so the unscaled originals (used by
        # IP for its interpolation ratio) mirror the scaled ones
        zone.get_unscaled_x()[i] = x
    zone.get_contour_ends()[0] = len(xs) - 1
    return zone


def _context(interp, glyph):
    ctx = interp.new_context(GraphicsState())
    ctx.set_ppem(16)
    ctx.set_glyph_zone(glyph)
    return ctx


def _set_point(zone, i, x, y):
    zone.get_current_x()[i] = x
    zone.get_current_y()[i] = y
    zone.get_original_x()[i] = x
    zone.get_original_y()[i] = y
    zone.get_unscaled_x()[i] = x
    zone.get_unscaled_y()[i] = y


def _run(interp, ctx, *program):
    interp.run(ctx, BytecodeStream(bytes(program)))


def test_projection_and_move():
    ctx = ExecutionContext(None, GraphicsState(), 16, [], None, Zone(0, 0))
    zone = _line_zone(100, 0)
    # default projection/freedom is the x axis: project returns the x coordinate
    assert ctx.project(zone.get_current_x()[0], zone.get_current_y()[0]) == 100
    ctx.move_point(zone, 0, 28)  # move +28 along x
    assert zone.get_current_x()[0] == 128
    assert zone.get_touched_x()[0]
    assert not zone.get_touched_y()[0]


def test_mdap_rounds_to_grid():
    interp = _interpreter()
    zone = _line_zone(100)  # 1.5625px
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB0, 0, 0x2F)  # PUSHB[0] 0 ; MDAP[1] (round)
    assert zone.get_current_x()[0] == 128  # rounded to 2px
    assert zone.get_touched_x()[0]


def test_mdrp_relative_to_rp0():
    interp = _interpreter()
    zone = _line_zone(0, 100)  # rp0 = point 0 at x=0, point 1 at 1.5625px
    ctx = _context(interp, zone)
    # PUSHB[0] 1 ; MDRP[round] (0xC4, round bit = 0x04) - grid-rounded distance from rp0
    _run(interp, ctx, 0xB0, 1, 0xC4)
    assert zone.get_current_x()[1] == 128  # distance 100 rounds to 128


def test_mdrp_scales_the_unscaled_original_distance():
    # MDRP measures the original distance in font units and scales it, rather than projecting the
    # individually rounded scaled originals (FreeType's Ins_MDRP, orus). From DejaVu Sans Bold '1'
    # at 14ppem: points 72 units apart at 2048 upem are 31.5/64 px apart. Scaled on their own they
    # land at 653 and 622, 31 apart, which rounds to 0; the scaled distance is 32, which rounds to
    # a pixel.
    interp = TrueTypeInterpreter(256, 16, 16, 2048)
    interp.set_ppem(14, 14)
    zone = Zone(2, 1)
    unscaled = [1493, 1421]
    for i in range(2):
        scaled = Fixed.scale(unscaled[i], 14, 2048)
        _set_point(zone, i, scaled, 0)
        zone.get_unscaled_x()[i] = unscaled[i]
    assert zone.get_current_x()[0] == 653
    assert zone.get_current_x()[1] == 622
    ctx = interp.new_context(GraphicsState())
    ctx.set_glyph_zone(zone)
    # PUSHB[0] 1 ; MDRP[round] (0xC4) relative to rp0 = point 0
    _run(interp, ctx, 0xB0, 1, 0xC4)
    assert zone.get_current_x()[1] == 653 - 64


def test_mdrp_round_and_minimum_distance_flags_are_distinct():
    # guards the flag encoding: round is bit 0x04, minimum-distance is bit 0x08. A small original
    # distance (30) below the minimum (64):
    interp = _interpreter()
    # round only (0xC4): 30 -> round(30) = 0, no minimum clamp
    round_zone = _line_zone(0, 30)
    _run(interp, _context(interp, round_zone), 0xB0, 1, 0xC4)
    assert round_zone.get_current_x()[1] == 0

    # minimum-distance only (0xC8): no rounding, but clamp the distance up to the minimum (64)
    min_zone = _line_zone(0, 30)
    _run(interp, _context(interp, min_zone), 0xB0, 1, 0xC8)
    assert min_zone.get_current_x()[1] == 64


def test_mirp_uses_control_value():
    interp = _interpreter()
    # raw cvt 128 at 16ppem / 1024 upem scales to 128 (2px)
    interp.set_control_values([128])
    interp.set_ppem(16, 16)
    zone = _line_zone(0, 100)
    ctx = interp.new_context(GraphicsState())
    ctx.set_ppem(16)
    ctx.set_glyph_zone(zone)
    # PUSHB[1] 1 0 (point=1 pushed first, cvtIndex=0 on top) ; MIRP[round] (0xE4, round = 0x04)
    _run(interp, ctx, 0xB1, 1, 0, 0xE4)
    assert zone.get_current_x()[1] == 128


def test_msirp_sets_exact_distance():
    interp = _interpreter()
    zone = _line_zone(0, 100)
    ctx = _context(interp, zone)
    # PUSHB[1] 1 64 (point=1, distance=1px) ; MSIRP[0] (0x3A)
    _run(interp, ctx, 0xB1, 1, 64, 0x3A)
    assert zone.get_current_x()[1] == 64  # exactly 1px from rp0 at x=0


def test_align_rp():
    interp = _interpreter()
    zone = _line_zone(0, 100)  # rp0 at 0
    ctx = _context(interp, zone)
    # PUSHB[0] 1 ; ALIGNRP (0x3C) - align point 1 onto rp0
    _run(interp, ctx, 0xB0, 1, 0x3C)
    assert zone.get_current_x()[1] == 0


def test_iup_interpolates_untouched():
    interp = _interpreter()
    # three points on one contour; the middle one is untouched
    zone = _line_zone(0, 50, 100)
    zone.get_touched_x()[0] = True
    zone.get_touched_x()[2] = True
    zone.get_current_x()[2] = 120  # the right anchor was hinted +20
    ctx = _context(interp, zone)
    _run(interp, ctx, 0x31)  # IUP[1] (x axis)
    # p1 interpolates proportionally: 0 + 50*(120-0)/100 = 60
    assert zone.get_current_x()[1] == 60
    # touched anchors are never moved by IUP
    assert zone.get_current_x()[0] == 0
    assert zone.get_current_x()[2] == 120


def test_iup_shifts_when_single_touched_point():
    interp = _interpreter()
    zone = _line_zone(0, 50, 100)
    zone.get_touched_x()[1] = True
    zone.get_current_x()[1] = 70  # the only touched point moved +20
    ctx = _context(interp, zone)
    _run(interp, ctx, 0x31)  # IUP[1]
    # with one touched point, every other point shifts by the same delta (+20)
    assert zone.get_current_x()[0] == 20
    assert zone.get_current_x()[2] == 120


def test_ip_interpolates_between_reference_points():
    interp = _interpreter()
    zone = _line_zone(0, 50, 100)
    # set rp1=0, rp2=2, move the anchors, then IP point 1
    zone.get_current_x()[2] = 120
    gs = GraphicsState()
    gs.set_rp1(0)
    gs.set_rp2(2)
    ctx = interp.new_context(gs)
    ctx.set_ppem(16)
    ctx.set_glyph_zone(zone)
    _run(interp, ctx, 0xB0, 1, 0x39)  # PUSHB[0] 1 ; IP (0x39)
    assert zone.get_current_x()[1] == 60


def test_ip_interpolates_twilight_points_using_scaled_originals():
    # Regression (PDFBOX-3293): twilight-zone points have no font-unit source, so their unscaled
    # coordinates are (0,0). Measuring IP's interpolation ratio against those zeros collapses
    # every interpolated point onto the reference point. For twilight points IP must measure the
    # scaled originals instead, exactly as FreeType's Ins_IP does.
    interp = _interpreter()
    gs = GraphicsState()
    gs.set_zp0(0)  # all three zone pointers reference the twilight zone
    gs.set_zp1(0)
    gs.set_zp2(0)
    gs.set_rp1(0)
    gs.set_rp2(2)
    ctx = interp.new_context(gs)
    ctx.set_ppem(16)
    twilight = ctx.get_twilight_zone()
    # anchors at originals 0 and 100; p2's current is stretched to 120. The unscaled coordinates
    # stay (0,0) for every point, exactly as MIAP leaves freshly placed twilight points.
    for p, x in enumerate((0, 50, 100)):
        twilight.get_original_x()[p] = x
        twilight.get_current_x()[p] = x
    twilight.get_current_x()[2] = 120
    _run(interp, ctx, 0xB0, 1, 0x39)  # PUSHB[0] 1 ; IP (0x39)
    # interpolate by the scaled originals: 0 + 50*(120-0)/100 = 60 (the unscaled zeros give 0)
    assert twilight.get_current_x()[1] == 60


def test_svtca_sets_projection_vector():
    interp = _interpreter()
    ctx = interp.new_context(GraphicsState())
    _run(interp, ctx, 0x00, 0x0C)  # SVTCA[0] (y axis) ; GPV
    assert ctx.peek(0) == Fixed.ONE_F2DOT14  # pv.y
    assert ctx.peek(1) == 0  # pv.x


def test_spvfs_normalizes_sign_extended_operands():
    # SPVFS takes the low 16 bits of each operand, sign-extended, and normalizes them (FreeType's
    # Ins_SPVFS); (0,0) leaves the vector as it was.
    interp = _interpreter()
    ctx = interp.new_context(GraphicsState())
    # PUSHW[1] 0xFFFF 0x0001 (x = -1 after sign extension, y = 1) ; SPVFS ; GPV
    _run(interp, ctx, 0xB9, 0xFF, 0xFF, 0x00, 0x01, 0x0A, 0x0C)
    assert ctx.peek(0) == 11585  # pv.y
    assert ctx.peek(1) == -11585  # pv.x
    # PUSHB[1] 0 0 ; SPVFS ; GPV - unchanged
    _run(interp, ctx, 0xB1, 0, 0, 0x0A, 0x0C)
    assert ctx.peek(0) == 11585
    assert ctx.peek(1) == -11585


def test_round_opcode():
    # PUSHB[0] 100 ; ROUND[0] (0x68) -> 128 under default round-to-grid
    ctx = _interpreter().execute_program(bytes([0xB0, 100, 0x68]), 16)
    assert ctx.peek(0) == 128


def test_md_measures_signed_distance():
    # MD measures project(zp0[p1] - zp1[p2]); p1 is the deeper operand, p2 the top (FreeType sign)
    interp = _interpreter()
    zone = _line_zone(0, 100)  # point 0 at x=0, point 1 at x=100
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB1, 0, 1, 0x49)  # PUSHB[1] 0 1 ; MD[grid] (0x49)
    assert ctx.peek(0) == -100  # x0 - x1 = -100


def test_gc_reads_projected_coordinate():
    interp = _interpreter()
    zone = _line_zone(192)  # 3px
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB0, 0, 0x46)  # PUSHB[0] 0 ; GC[0] (0x46) current coordinate
    assert ctx.peek(0) == 192


def test_isect_moves_point_to_line_intersection():
    interp = _interpreter()
    # p0 = the point to move; line A = horizontal y=64 (p1,p2); line B = vertical x=64 (p3,p4)
    zone = Zone(5, 1)
    _set_point(zone, 0, 0, 0)
    _set_point(zone, 1, 0, 64)
    _set_point(zone, 2, 128, 64)
    _set_point(zone, 3, 64, 0)
    _set_point(zone, 4, 64, 128)
    ctx = _context(interp, zone)
    # push p0,a0,a1,b0,b1 = 0 1 2 3 4 ; ISECT (0x0F) pops b1,b0,a1,a0,point
    _run(interp, ctx, 0xB4, 0, 1, 2, 3, 4, 0x0F)
    assert zone.get_current_x()[0] == 64
    assert zone.get_current_y()[0] == 64
    assert zone.get_touched_x()[0]
    assert zone.get_touched_y()[0]


# --- oracle-free invariant checks ------------------------------------


def test_iup_never_moves_a_touched_point():
    # invariant: IUP leaves every already-touched point exactly where it is
    interp = _interpreter()
    zone = _line_zone(0, 50, 100)
    zone.get_touched_x()[1] = True
    zone.get_current_x()[1] = 77  # a touched point at a deliberately off-grid position
    ctx = _context(interp, zone)
    _run(interp, ctx, 0x31)  # IUP[x]
    assert zone.get_current_x()[1] == 77


def test_touched_points_land_on_grid_under_round_to_grid():
    # invariant: under an integer round state, a rounded (touched) point lands on a grid line
    interp = _interpreter()
    zone = _line_zone(100, 150, 77)  # off-grid positions
    ctx = _context(interp, zone)  # default round state is round-to-grid
    _run(interp, ctx, 0xB0, 0, 0x2F, 0xB0, 1, 0x2F, 0xB0, 2, 0x2F)  # MDAP[1] each point
    for i in range(3):
        assert zone.get_touched_x()[i], f"point {i} should be touched"
        assert zone.get_current_x()[i] % Fixed.ONE == 0, f"point {i} off the grid"


def test_spvtl_line_runs_from_top_point_to_lower_point():
    # SPVTL takes the top point from zp2 and the one below it from zp1, and the line runs from the
    # zp2 point to the zp1 point (FreeType's Ins_SxVTL). Here that is (64,0) to (0,0), so the
    # projection vector is -x and GC of the point at x=64 reads -64.
    interp = _interpreter()
    zone = Zone(2, 1)
    _set_point(zone, 0, 64, 0)
    _set_point(zone, 1, 0, 0)
    ctx = _context(interp, zone)
    # PUSHB[1] 1 0 (zp1 point 1 below, zp2 point 0 on top) ; SPVTL[0] ; PUSHB[0] 0 ; GC[0]
    _run(interp, ctx, 0xB1, 1, 0, 0x06, 0xB0, 0, 0x46)
    assert ctx.get_graphics_state().get_projection_vector().get_x() == -Fixed.ONE_F2DOT14
    assert ctx.peek(0) == -64


def test_spvtl_sets_dual_vector_to_projection_vector():
    # SPVTL sets the dual projection vector equal to the projection vector; only SDPVTL derives it
    # from the original outline (FreeType's Ins_SPVTL). The current line here is horizontal while
    # the original line is vertical, so a dual vector taken from the originals would be the y axis.
    interp = _interpreter()
    zone = Zone(2, 1)
    _set_point(zone, 0, 0, 0)
    _set_point(zone, 1, 0, 64)
    zone.get_current_x()[1] = 64
    zone.get_current_y()[1] = 0
    ctx = _context(interp, zone)
    # PUSHB[1] 1 0 ; SPVTL[0] ; PUSHB[0] 1 ; GC[1] (original, along the dual vector)
    _run(interp, ctx, 0xB1, 1, 0, 0x06, 0xB0, 1, 0x47)
    dual = ctx.get_graphics_state().get_dual_projection_vector()
    assert dual.get_x() == Fixed.ONE_F2DOT14
    assert dual.get_y() == 0
    assert ctx.peek(0) == 0  # original (0,64) projected on the x axis


def test_spvtl_zero_length_line_is_x_axis_even_when_perpendicular():
    # a zero-length line gives the x axis even for the perpendicular form (FreeType's Ins_SxVTL)
    interp = _interpreter()
    zone = Zone(1, 1)
    _set_point(zone, 0, 64, 64)
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB1, 0, 0, 0x07)  # PUSHB[1] 0 0 ; SPVTL[1] (perpendicular)
    pv = ctx.get_graphics_state().get_projection_vector()
    assert pv.get_x() == Fixed.ONE_F2DOT14
    assert pv.get_y() == 0


def test_sdpvtl_zero_length_original_line_drops_perpendicular_for_current_line():
    # SDPVTL: when the original line has zero length FreeType drops the perpendicular flag, and
    # the drop carries over to the current line computed after it, so the projection vector runs
    # along the current line rather than across it.
    interp = _interpreter()
    zone = Zone(2, 1)
    _set_point(zone, 0, 0, 0)
    _set_point(zone, 1, 0, 0)
    zone.get_current_x()[1] = 64
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB1, 1, 0, 0x87)  # PUSHB[1] 1 0 ; SDPVTL[1] (perpendicular)
    pv = ctx.get_graphics_state().get_projection_vector()
    dual = ctx.get_graphics_state().get_dual_projection_vector()
    assert pv.get_x() == Fixed.ONE_F2DOT14
    assert pv.get_y() == 0
    assert dual.get_x() == Fixed.ONE_F2DOT14
    assert dual.get_y() == 0


def _context_with_cvt128(interp, glyph):
    """An interpreter whose cvt[0] scales to 128 (2px) at 16ppem, and a context on the zone."""
    interp.set_control_values([128])
    interp.set_ppem(16, 16)
    return _context(interp, glyph)


def test_mirp_places_twilight_point_from_rp0():
    # MIRP to a twilight point first places it the control value away from rp0's original
    # position along the freedom vector (undocumented MS rasterizer behaviour, FreeType's
    # Ins_MIRP). Without that the point's stale origin at 0 would flip the control value to -128.
    interp = _interpreter()
    ctx = _context_with_cvt128(interp, _line_zone(64))  # rp0 = glyph point 0 at 1px
    # PUSHB[0] 0 ; SZP1 (twilight) ; PUSHB[1] 3 0 ; MIRP[0] (no round, no minimum)
    _run(interp, ctx, 0xB0, 0, 0x14, 0xB1, 3, 0, 0xE0)
    twilight = ctx.get_twilight_zone()
    assert twilight.get_original_x()[3] == 192
    assert twilight.get_current_x()[3] == 192


def test_msirp_places_twilight_point_from_rp0():
    # MSIRP to a twilight point first places its original position the distance away from rp0's
    # original position (undocumented MS rasterizer behaviour, FreeType's Ins_MSIRP).
    interp = _interpreter()
    ctx = _context(interp, _line_zone(64))  # rp0 = glyph point 0 at 1px
    # PUSHB[0] 0 ; SZP1 (twilight) ; PUSHB[1] 3 64 ; MSIRP[0]
    _run(interp, ctx, 0xB0, 0, 0x14, 0xB1, 3, 64, 0x3A)
    twilight = ctx.get_twilight_zone()
    assert twilight.get_original_x()[3] == 128
    assert twilight.get_current_x()[3] == 128


def test_miap_places_twilight_point_along_freedom_vector():
    # MIAP on a twilight point places its origin at the control value along the freedom vector,
    # not the projection vector (FreeType's Ins_MIAP). With a diagonal freedom vector and an
    # x-axis projection the difference shows in the original y.
    interp = _interpreter()
    ctx = _context_with_cvt128(interp, _line_zone(0))
    diagonal = 0x2D41  # 1/sqrt(2) in F2Dot14
    # PUSHB[0] 0 ; SZP0 (twilight) ; PUSHW[1] diagonal diagonal ; SFVFS ; PUSHB[1] 3 0 ; MIAP[0]
    _run(interp, ctx, 0xB0, 0, 0x13, 0xB9, 0x2D, 0x41, 0x2D, 0x41, 0x0B, 0xB1, 3, 0, 0x3E)
    twilight = ctx.get_twilight_zone()
    assert twilight.get_original_x()[3] == Fixed.mul14(128, diagonal)
    assert twilight.get_original_y()[3] == Fixed.mul14(128, diagonal)
    assert twilight.get_current_x()[3] == 128  # then moved along fv until its x projects to 128


def test_isect_parallel_lines_use_the_average_of_the_four_points():
    # ISECT on parallel lines (zero discriminant) cannot intersect them; like FreeType it moves
    # the point to the average of the four line points.
    interp = _interpreter()
    zone = Zone(5, 1)
    _set_point(zone, 0, 0, 0)
    _set_point(zone, 1, 0, 0)  # line A: y = 0
    _set_point(zone, 2, 128, 0)
    _set_point(zone, 3, 0, 64)  # line B: y = 64, parallel to A
    _set_point(zone, 4, 128, 64)
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB4, 0, 1, 2, 3, 4, 0x0F)  # ISECT
    assert zone.get_current_x()[0] == 64  # (0 + 128 + 0 + 128) / 4
    assert zone.get_current_y()[0] == 32  # (0 + 0 + 64 + 64) / 4


def test_align_pts_moves_each_point_by_half_the_distance():
    # ALIGNPTS moves each point by half their projected distance, truncated, towards the other
    # (FreeType's Ins_ALIGNPTS): 127/64 px apart, each moves 63, leaving them 1/64 px apart.
    interp = _interpreter()
    zone = _line_zone(0, 127)
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB1, 0, 1, 0x27)  # ALIGNPTS
    assert zone.get_current_x()[0] == 63
    assert zone.get_current_x()[1] == 64


def test_utp_untouches_only_the_freedom_axes():
    interp = _interpreter()
    zone = _line_zone(0, 64)
    zone.get_touched_x()[1] = True
    zone.get_touched_y()[1] = True
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB0, 1, 0x29)  # UTP (fv = x)
    assert not zone.get_touched_x()[1]
    assert zone.get_touched_y()[1]


def test_flip_pt_toggles_on_curve():
    interp = _interpreter()
    zone = _line_zone(0, 64)
    zone.get_on_curve()[1] = True
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB0, 1, 0x80)  # FLIPPT
    assert not zone.get_on_curve()[1]
    _run(interp, ctx, 0xB0, 1, 0x80)
    assert zone.get_on_curve()[1]


def test_shc_ignores_an_invalid_contour():
    # SHC with a contour the zone does not have is ignored, as in FreeType outside pedantic mode
    interp = _interpreter()
    zone = _line_zone(0, 64)
    zone.get_current_x()[0] = 32  # rp2 = point 0 moved by 32
    ctx = _context(interp, zone)
    _run(interp, ctx, 0xB0, 5, 0x34)  # SHC[0] contour 5
    assert zone.get_current_x()[1] == 64


def test_shc_shifts_the_whole_twilight_zone():
    # In the twilight zone SHC treats all points as one contour (FreeType's Ins_SHC): contour 0
    # shifts every twilight point by the reference point's movement.
    interp = _interpreter()
    zone = _line_zone(0, 64)
    zone.get_current_x()[0] = 64  # rp1 = glyph point 0, moved by 64
    ctx = _context(interp, zone)
    # PUSHB[0] 0 ; SZP2 (twilight) ; PUSHB[0] 0 ; SHC[1] (rp1 in zp0 = glyph zone)
    _run(interp, ctx, 0xB0, 0, 0x15, 0xB0, 0, 0x35)
    twilight = ctx.get_twilight_zone()
    assert twilight.get_current_x()[0] == 64
    assert twilight.get_current_x()[15] == 64


def test_iup_does_nothing_once_both_axes_are_done_under_backward_compatibility():
    # Under backward compatibility, once IUP has run on both axes further IUPs do nothing
    # (FreeType's Ins_IUP), so a late y move is not spread over the untouched points.
    interp = _interpreter()
    zone = _line_zone(0, 64, 128)
    zone.get_current_y()[0] = 64
    zone.get_touched_y()[0] = True
    ctx = _context(interp, zone)
    ctx.set_backward_compatibility(True)
    _run(interp, ctx, 0x30, 0x31)  # IUP[y], IUP[x]
    assert zone.get_current_y()[1] == 64  # shifted with the single touched point
    zone.get_current_y()[0] = 128
    _run(interp, ctx, 0x30)  # IUP[y] again: ignored
    assert zone.get_current_y()[1] == 64


_B1 = 0xB0  # PUSHB[0], one byte
_B2 = 0xB1  # PUSHB[1], two bytes
_B5 = 0xB4  # PUSHB[4], five bytes

_OUT_OF_RANGE_POINT_PROGRAMS = [
    ("MDAP", [_B1, 99, 0x2E]),
    ("MIAP", [_B2, 99, 0, 0x3E]),
    ("MSIRP", [_B2, 99, 64, 0x3A]),
    ("MDRP", [_B1, 99, 0xC0]),
    ("MIRP", [_B2, 99, 0, 0xE0]),
    ("ALIGNRP", [_B1, 99, 0x3C]),
    ("ALIGNPTS", [_B2, 0, 99, 0x27]),
    ("UTP", [_B1, 99, 0x29]),
    ("SHPIX", [_B2, 99, 64, 0x38]),
    ("SHP", [_B1, 99, 0x32]),
    ("IP", [_B1, 99, 0x39]),
    ("GC", [_B1, 99, 0x46]),
    ("SCFS", [_B2, 99, 0, 0x48]),
    ("MD", [_B2, 0, 99, 0x49]),
    ("ISECT", [_B5, 99, 0, 1, 0, 1, 0x0F]),
    ("SPVTL", [_B2, 0, 99, 0x06]),
    ("FLIPPT", [_B1, 99, 0x80]),
    ("SRP0 then MDRP", [_B1, 99, 0x10, _B1, 1, 0xC0]),
    ("SRP1 then IP", [_B1, 99, 0x11, _B1, 1, 0x39]),
    ("SRP2 then SHP", [_B1, 99, 0x12, _B1, 1, 0x32]),
]


@pytest.mark.parametrize(
    "program",
    [p for _, p in _OUT_OF_RANGE_POINT_PROGRAMS],
    ids=[n for n, _ in _OUT_OF_RANGE_POINT_PROGRAMS],
)
def test_out_of_range_point_is_a_hinting_exception(program):
    # An out-of-range point number - an operand, or a reference point set with SRPn - is malformed
    # font data: it must fail as a HintingException, which falls back to the raw glyph, not as an
    # index error, which would escape to the renderer. The zone has two points (and the twilight
    # zone 16), so point 99 exists in neither.
    interp = _interpreter()
    ctx = _context(interp, _line_zone(0, 64))
    with pytest.raises(HintingException):
        interp.run(ctx, BytecodeStream(bytes(program)))

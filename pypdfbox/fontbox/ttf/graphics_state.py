"""The TrueType interpreter graphics state.

Projection/freedom vectors, reference and zone pointers, round state, and the
various cut-ins and distances. Two operations carry the correctness burden:

* :meth:`GraphicsState.copy` performs a *deep* copy of the
  :class:`UnitVector` fields, so mutating a per-glyph clone never contaminates
  the saved post-``prep`` template.
* :meth:`GraphicsState.reset_for_glyph` resets only the fields the TrueType
  spec re-initializes at the start of each glyph program (the vectors,
  reference points, zone pointers and loop counter), while leaving the values
  established by ``prep`` (round state, cut-ins, delta base/shift, etc.)
  intact.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.fixed import HALF, ONE, ONE_F2DOT14, int_div, to_int32
from pypdfbox.fontbox.ttf.unit_vector import UnitVector

# SROUND/S45ROUND period selector (bits 7-6) to the period in half grid periods.
_PERIOD_HALVES = (1, 2, 4, 2)

# above this magnitude the Java int intermediates of round() may wrap
_ROUND_FAST_LIMIT = 0x40000000


class GraphicsState:
    """Mirrors upstream package-private ``GraphicsState``."""

    ROUND_TO_GRID = 0
    """Round to grid - the default round state."""
    ROUND_TO_HALF_GRID = 1
    """Round to half grid."""
    ROUND_TO_DOUBLE_GRID = 2
    """Round to double grid."""
    ROUND_DOWN_TO_GRID = 3
    """Round down to grid."""
    ROUND_UP_TO_GRID = 4
    """Round up to grid."""
    ROUND_OFF = 5
    """Rounding off."""
    ROUND_SUPER = 6
    """Super round (set by SROUND)."""
    ROUND_SUPER_45 = 7
    """Super round 45 degrees (set by S45ROUND)."""

    __slots__ = (
        "_auto_flip",
        "_control_value_cut_in",
        "_delta_base",
        "_delta_shift",
        "_dual_projection_vector",
        "_freedom_vector",
        "_instruct_control",
        "_loop",
        "_minimum_distance",
        "_projection_vector",
        "_round_off",
        "_round_period",
        "_round_phase",
        "_round_state",
        "_round_threshold",
        "_rp0",
        "_rp1",
        "_rp2",
        "_scan_control",
        "_scan_type",
        "_single_width_cut_in",
        "_single_width_value",
        "_zp0",
        "_zp1",
        "_zp2",
    )

    def __init__(self, src: GraphicsState | None = None) -> None:
        """Creates a graphics state with the spec-mandated default values.

        This is the state before the font's ``fpgm``/``prep`` programs run.
        ``src`` is the private copy-constructor path used by :meth:`copy`.
        """
        if src is not None:
            self._copy_from(src)
            return
        self._projection_vector = UnitVector.x_axis()
        self._freedom_vector = UnitVector.x_axis()
        self._dual_projection_vector = UnitVector.x_axis()
        self._rp0 = 0
        self._rp1 = 0
        self._rp2 = 0
        self._zp0 = 1
        self._zp1 = 1
        self._zp2 = 1
        self._loop = 1
        self._round_period = 0
        self._round_phase = 0
        self._round_threshold = 0
        self._round_off = False
        self.set_round_state(GraphicsState.ROUND_TO_GRID)
        self._minimum_distance = ONE  # 1 pixel
        self._control_value_cut_in = 17 * ONE // 16  # 17/16 pixel = 68
        self._single_width_cut_in = 0
        self._single_width_value = 0
        self._delta_base = 9
        self._delta_shift = 3
        self._auto_flip = True
        self._scan_control = 0
        self._scan_type = 0
        self._instruct_control = 0

    def _copy_from(self, src: GraphicsState) -> None:
        self._projection_vector = src._projection_vector.copy()
        self._freedom_vector = src._freedom_vector.copy()
        self._dual_projection_vector = src._dual_projection_vector.copy()
        self._rp0 = src._rp0
        self._rp1 = src._rp1
        self._rp2 = src._rp2
        self._zp0 = src._zp0
        self._zp1 = src._zp1
        self._zp2 = src._zp2
        self._loop = src._loop
        self._round_state = src._round_state
        self._round_period = src._round_period
        self._round_phase = src._round_phase
        self._round_threshold = src._round_threshold
        self._round_off = src._round_off
        self._minimum_distance = src._minimum_distance
        self._control_value_cut_in = src._control_value_cut_in
        self._single_width_cut_in = src._single_width_cut_in
        self._single_width_value = src._single_width_value
        self._delta_base = src._delta_base
        self._delta_shift = src._delta_shift
        self._auto_flip = src._auto_flip
        self._scan_control = src._scan_control
        self._scan_type = src._scan_type
        self._instruct_control = src._instruct_control

    def copy(self) -> GraphicsState:
        """Returns an independent deep copy, with the :class:`UnitVector` fields cloned."""
        return GraphicsState(self)

    def reset_for_glyph(self) -> None:
        """Resets the per-glyph fields to their defaults, as the spec requires per glyph program.

        The projection, freedom and dual-projection vectors return to the x
        axis; the reference points reset to 0; the zone pointers reset to the
        glyph zone (1); the loop counter resets to 1. Fields configured by
        ``prep`` (round state, cut-ins, minimum distance, delta base/shift,
        single width, auto-flip, scan control) are left untouched.
        """
        self._projection_vector.set(ONE_F2DOT14, 0)
        self._freedom_vector.set(ONE_F2DOT14, 0)
        self._dual_projection_vector.set(ONE_F2DOT14, 0)
        self._rp0 = 0
        self._rp1 = 0
        self._rp2 = 0
        self._zp0 = 1
        self._zp1 = 1
        self._zp2 = 1
        self._loop = 1

    def get_projection_vector(self) -> UnitVector:
        return self._projection_vector

    def get_freedom_vector(self) -> UnitVector:
        return self._freedom_vector

    def get_dual_projection_vector(self) -> UnitVector:
        return self._dual_projection_vector

    def get_rp0(self) -> int:
        return self._rp0

    def set_rp0(self, value: int) -> None:
        self._rp0 = value

    def get_rp1(self) -> int:
        return self._rp1

    def set_rp1(self, value: int) -> None:
        self._rp1 = value

    def get_rp2(self) -> int:
        return self._rp2

    def set_rp2(self, value: int) -> None:
        self._rp2 = value

    def get_zp0(self) -> int:
        return self._zp0

    def set_zp0(self, value: int) -> None:
        self._zp0 = value

    def get_zp1(self) -> int:
        return self._zp1

    def set_zp1(self, value: int) -> None:
        self._zp1 = value

    def get_zp2(self) -> int:
        return self._zp2

    def set_zp2(self, value: int) -> None:
        self._zp2 = value

    def get_loop(self) -> int:
        return self._loop

    def set_loop(self, value: int) -> None:
        self._loop = value

    def get_round_state(self) -> int:
        return self._round_state

    def set_round_state(self, value: int) -> None:
        """Sets the round state and derives the period/phase/threshold :meth:`round` uses.

        The simple states are expressed as special cases of the super-round
        parameters. ``SROUND`` and ``S45ROUND`` call :meth:`set_super_round`
        instead.
        """
        self._round_state = value
        self._round_off = False
        if value == GraphicsState.ROUND_TO_GRID:
            self._round_period = ONE
            self._round_phase = 0
            self._round_threshold = HALF
        elif value == GraphicsState.ROUND_TO_HALF_GRID:
            self._round_period = ONE
            self._round_phase = HALF
            self._round_threshold = HALF
        elif value == GraphicsState.ROUND_TO_DOUBLE_GRID:
            self._round_period = HALF
            self._round_phase = 0
            self._round_threshold = HALF // 2
        elif value == GraphicsState.ROUND_DOWN_TO_GRID:
            self._round_period = ONE
            self._round_phase = 0
            self._round_threshold = 0
        elif value == GraphicsState.ROUND_UP_TO_GRID:
            self._round_period = ONE
            self._round_phase = 0
            self._round_threshold = ONE - 1
        elif value == GraphicsState.ROUND_OFF:
            self._round_off = True
        # ROUND_SUPER / ROUND_SUPER_45 are configured by set_super_round

    def set_super_round(self, grid_period: int, selector: int) -> None:
        """Configures super-round parameters for ``SROUND``/``S45ROUND`` from the selector byte.

        The period, phase and threshold are derived in F2Dot14 and then
        converted to F26Dot6, exactly as FreeType's ``SetSuperRound`` does;
        deriving them in F26Dot6 directly is off by one for the S45ROUND
        "period - 1" threshold (44 instead of 45).

        ``grid_period`` is the base grid period in F2Dot14 (``0x4000`` = one
        pixel for SROUND; ``0x2D41`` = sqrt(2)/2, the diagonal, for S45ROUND).
        """
        # bits 7-6: the period as a multiple of the grid, in halves - 1/2, 1, 2, and the reserved
        # value 3 taken as 1 (as FreeType does); bits 5-4: the phase in quarters of the period
        period = int_div(grid_period * _PERIOD_HALVES[(selector >> 6) & 3], 2)
        phase = int_div(period * ((selector >> 4) & 3), 4)
        n = selector & 0x0F
        threshold = period - 1 if n == 0 else int_div((n - 4) * period, 8)

        # F2Dot14 -> F26Dot6
        self._round_period = max(1, period >> 8)
        self._round_phase = phase >> 8
        self._round_threshold = threshold >> 8
        # upstream records ROUND_SUPER for S45ROUND too
        self._round_state = GraphicsState.ROUND_SUPER
        self._round_off = False

    def round(self, distance: int) -> int:
        """Rounds a distance (F26Dot6) according to the current round state.

        Engine compensation (the black/white/grey distance bias FreeType
        applies) is treated as zero, which is correct for an anti-aliased
        target.
        """
        if self._round_off:
            return distance
        phase = self._round_phase
        period = self._round_period
        if -_ROUND_FAST_LIMIT < distance < _ROUND_FAST_LIMIT:
            if distance >= 0:
                val = (distance - phase + self._round_threshold) // period * period
                if val < 0:
                    val = 0
                return val + phase
            val = -((self._round_threshold - phase - distance) // period * period)
            if val > 0:
                val = 0
            return val - phase
        return self._round_wrapping(distance)

    def _round_wrapping(self, distance: int) -> int:
        """:meth:`round` with every Java ``int`` intermediate narrowed, for huge distances."""
        phase = self._round_phase
        period = self._round_period
        threshold = self._round_threshold
        if distance >= 0:
            t = to_int32(to_int32(distance - phase) + threshold)
            val = to_int32((t // period) * period)
            if val < 0:
                val = 0
            return to_int32(val + phase)
        t = to_int32(to_int32(threshold - phase) - distance)
        val = to_int32(-to_int32((t // period) * period))
        if val > 0:
            val = 0
        return to_int32(val - phase)

    def get_minimum_distance(self) -> int:
        return self._minimum_distance

    def set_minimum_distance(self, value: int) -> None:
        self._minimum_distance = value

    def get_control_value_cut_in(self) -> int:
        return self._control_value_cut_in

    def set_control_value_cut_in(self, value: int) -> None:
        self._control_value_cut_in = value

    def get_single_width_cut_in(self) -> int:
        return self._single_width_cut_in

    def set_single_width_cut_in(self, value: int) -> None:
        self._single_width_cut_in = value

    def get_single_width_value(self) -> int:
        return self._single_width_value

    def set_single_width_value(self, value: int) -> None:
        self._single_width_value = value

    def get_delta_base(self) -> int:
        return self._delta_base

    def set_delta_base(self, value: int) -> None:
        self._delta_base = value

    def get_delta_shift(self) -> int:
        return self._delta_shift

    def set_delta_shift(self, value: int) -> None:
        self._delta_shift = value

    def is_auto_flip(self) -> bool:
        return self._auto_flip

    def set_auto_flip(self, value: bool) -> None:
        self._auto_flip = value

    def get_scan_control(self) -> int:
        return self._scan_control

    def set_scan_control(self, value: int) -> None:
        self._scan_control = value

    def get_scan_type(self) -> int:
        return self._scan_type

    def set_scan_type(self, value: int) -> None:
        self._scan_type = value

    def get_instruct_control(self) -> int:
        return self._instruct_control

    def set_instruct_control(self, value: int) -> None:
        self._instruct_control = value


__all__ = ["GraphicsState"]

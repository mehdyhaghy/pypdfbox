"""All mutable state for a single run of the TrueType interpreter.

Bundled into one object so opcode handlers share a uniform
``handler(ctx)`` signature and new state can be added without touching every
handler. It holds the operand stack, storage area, scaled control values, the
two point zones, the :class:`GraphicsState`, the current
:class:`BytecodeStream`, and the ppem the program is running at.

Not all of that state is per-run. The storage area and the twilight zone are
owned by the :class:`TrueTypeInterpreter` and handed to every context at one
size, because a font may compute values into them in ``prep`` and read them
back from each glyph program - FreeType keeps both on the ``TT_Size`` for the
same reason.

Performance notes: the operand stack is a Python ``list`` used with
``append``/``pop`` (the capacity is still enforced on every growing opcode),
and the vector objects of the graphics state are cached on the context, which
is safe because upstream never replaces them, it only ``set``\\ s them.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pypdfbox.fontbox.ttf.fixed import ONE_F2DOT14, mul_div
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.hinting_exception import HintingException
from pypdfbox.fontbox.ttf.zone import Zone

if TYPE_CHECKING:
    from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
    from pypdfbox.fontbox.ttf.true_type_interpreter import TrueTypeInterpreter

_INT_MIN = -0x80000000
_INT_MAX = 0x7FFFFFFF


def _i32(value: int) -> int:
    return ((value + 0x80000000) & 0xFFFFFFFF) - 0x80000000


class ExecutionContext:
    """Mirrors upstream package-private ``ExecutionContext``."""

    class CodeRange(Enum):
        """The top-level program a context runs, after FreeType's code ranges.

        Some instructions behave differently depending on it: INSTCTRL, for
        one, only takes effect in ``prep``.
        """

        FONT = "FONT"
        """the font program, ``fpgm``"""
        CONTROL_VALUE = "CONTROL_VALUE"
        """the control value program, ``prep``"""
        GLYPH = "GLYPH"
        """a glyph program"""

    __slots__ = (
        "_backward_compatibility",
        "_call_depth",
        "_code_range",
        "_composite",
        "_control_values",
        "_dv",
        "_execution_budget",
        "_fv",
        "_glyph_zone",
        "_graphics_state",
        "_interpreter",
        "_iupx_called",
        "_iupy_called",
        "_loop_call_counter",
        "_negative_jump_counter",
        "_point_size",
        "_ppem",
        "_pv",
        "_return_from_function",
        "_stack",
        "_stack_capacity",
        "_storage",
        "_stream",
        "_twilight_zone",
        "_units_per_em",
    )

    def __init__(
        self,
        interpreter: TrueTypeInterpreter | None,
        graphics_state: GraphicsState,
        max_stack_elements: int,
        storage: list[int],
        control_values: list[int] | None,
        twilight_zone: Zone,
    ) -> None:
        """Creates a context.

        ``storage`` and ``twilight_zone`` are the interpreter's, shared across
        the runs at one size; ``control_values`` are the scaled control values
        (F26Dot6), or ``None``.
        """
        self._interpreter = interpreter
        self._graphics_state = graphics_state
        self._pv = graphics_state._projection_vector
        self._fv = graphics_state._freedom_vector
        self._dv = graphics_state._dual_projection_vector
        self._stack: list[int] = []
        self._stack_capacity = max(max_stack_elements, 1)
        self._storage = storage
        self._control_values = control_values if control_values is not None else []
        self._twilight_zone = twilight_zone
        self._glyph_zone: Zone | None = None
        self._ppem = 0
        self._point_size = 0
        self._units_per_em = 0
        self._stream: BytecodeStream | None = None
        self._call_depth = 0
        self._return_from_function = False
        # Execution budget. TrueType can only loop through a backward jump or a LOOPCALL, so
        # bounding those two bounds the whole program - without them a four-byte glyph program can
        # spin forever. Both counters are per-context, and one context is one top-level program
        # run, so they need no reset. After FreeType's neg_jump_counter / loopcall_counter in
        # TT_RunIns.
        self._negative_jump_counter = 0
        self._loop_call_counter = 0
        self._execution_budget = -1
        # v40 "backward compatibility" (grayscale subpixel) state. When set, point moves in the x
        # direction are suppressed so stems are not grid-fit and darkened under antialiasing, and y
        # moves are frozen once IUP has run on both axes. Only enabled for the glyph program, never
        # fpgm/prep.
        self._backward_compatibility = False
        self._code_range = ExecutionContext.CodeRange.GLYPH
        self._iupx_called = False
        self._iupy_called = False
        self._composite = False

    def get_interpreter(self) -> TrueTypeInterpreter | None:
        """Returns the owning interpreter."""
        return self._interpreter

    def get_graphics_state(self) -> GraphicsState:
        """Returns the graphics state."""
        return self._graphics_state

    # --- operand stack ---------------------------------------------------

    def push(self, value: int) -> None:
        """Pushes a value onto the operand stack; raises on overflow."""
        stack = self._stack
        if len(stack) >= self._stack_capacity:
            raise HintingException(f"interpreter stack overflow at {len(stack)}")
        stack.append(value)

    def pop(self) -> int:
        """Pops a value from the operand stack; raises on underflow."""
        if not self._stack:
            raise HintingException("interpreter stack underflow")
        return self._stack.pop()

    def peek(self, n: int) -> int:
        """Returns the value ``n`` positions below the top (``peek(0)`` is the top)."""
        depth = len(self._stack)
        index = depth - 1 - n
        if index < 0 or index >= depth:
            raise HintingException(f"interpreter stack peek out of range: {n}")
        return self._stack[index]

    def get_stack_depth(self) -> int:
        """Returns the current stack depth."""
        return len(self._stack)

    def clear_stack(self) -> None:
        """Empties the operand stack."""
        self._stack.clear()

    # --- execution budget -------------------------------------------------

    def get_execution_budget(self) -> int:
        """The maximum number of backward jumps, and separately of LOOPCALL iterations, per run.

        Sized the way FreeType's TT_RunIns sizes its counters, so a
        legitimately loop-heavy program still completes while a crafted one
        cannot run forever: from the glyph's point count and the control value
        count for a glyph program, and from the control value count alone for
        fpgm/prep, which typically loop over every CVT entry. Computed on first
        use, because the glyph zone is attached after the context is built.
        """
        if self._execution_budget < 0:
            points = self._glyph_zone._point_count if self._glyph_zone is not None else 0
            cvt_count = len(self._control_values)
            self._execution_budget = (
                max(50, 10 * points) + max(50, cvt_count // 10)
                if points > 0
                else 300 + 22 * cvt_count
            )
        return self._execution_budget

    def count_negative_jump(self) -> None:
        """Records one backward jump, failing the run once the budget is exhausted."""
        self._negative_jump_counter += 1
        if self._negative_jump_counter > self.get_execution_budget():
            raise HintingException(
                f"too many backward jumps, limit is {self.get_execution_budget()}"
            )

    def count_loop_calls(self, count: int) -> None:
        """Adds ``count`` iterations to the LOOPCALL budget, failing before the loop is entered.

        The budget is cumulative across the run, so a program cannot slip past
        it by issuing many small loops.
        """
        self._loop_call_counter += count
        if self._loop_call_counter > self.get_execution_budget():
            raise HintingException(
                f"LOOPCALL runs too long, limit is {self.get_execution_budget()}"
                f" iterations, asked for {self._loop_call_counter}"
            )

    # --- storage and control values --------------------------------------

    def get_storage(self) -> list[int]:
        """Returns the storage area, shared with every other run at this size."""
        return self._storage

    def get_control_values(self) -> list[int]:
        """Returns the scaled control values in F26Dot6."""
        return self._control_values

    # --- zones -----------------------------------------------------------

    def get_twilight_zone(self) -> Zone:
        """Returns the twilight zone (zone 0), shared with every other run at this size."""
        return self._twilight_zone

    def get_glyph_zone(self) -> Zone | None:
        """Returns the glyph zone (zone 1), or ``None`` if no glyph is loaded."""
        return self._glyph_zone

    def set_glyph_zone(self, zone: Zone | None) -> None:
        self._glyph_zone = zone

    def get_zone(self, zone_pointer: int) -> Zone:
        """Resolves a zone pointer (0 = twilight, 1 = glyph) to its :class:`Zone`."""
        if zone_pointer == 1:
            zone = self._glyph_zone
            if zone is None:
                raise HintingException("glyph zone referenced but not loaded")
            return zone
        if zone_pointer == 0:
            return self._twilight_zone
        raise HintingException(f"invalid zone pointer: {zone_pointer}")

    # --- sizing ----------------------------------------------------------

    def get_ppem(self) -> int:
        return self._ppem

    def set_ppem(self, value: int) -> None:
        self._ppem = value

    def get_point_size(self) -> int:
        return self._point_size

    def set_point_size(self, value: int) -> None:
        self._point_size = value

    def get_units_per_em(self) -> int:
        return self._units_per_em

    def set_units_per_em(self, value: int) -> None:
        self._units_per_em = value

    # --- projection / freedom vector math --------------------------------

    @staticmethod
    def dot14(ax: int, ay: int, bx: int, by: int) -> int:
        """Dot product shifted back down by 14 bits with rounding: the projection primitive.

        Projecting an F26Dot6 coordinate onto an F2Dot14 unit vector yields an
        F26Dot6 distance.
        """
        r = (ax * bx + ay * by + 0x2000) >> 14
        return r if _INT_MIN <= r <= _INT_MAX else _i32(r)

    def project(self, x: int, y: int) -> int:
        """Projects a coordinate (F26Dot6) onto the projection vector."""
        pv = self._pv
        r = (x * pv._x + y * pv._y + 0x2000) >> 14
        return r if _INT_MIN <= r <= _INT_MAX else _i32(r)

    def dual_project(self, x: int, y: int) -> int:
        """Projects a coordinate onto the dual projection vector (for original positions)."""
        dv = self._dv
        r = (x * dv._x + y * dv._y + 0x2000) >> 14
        return r if _INT_MIN <= r <= _INT_MAX else _i32(r)

    def projected_distance(self, zone1: Zone, p1: int, zone0: Zone, p0: int) -> int:
        """Current (hinted) distance from ``p0`` in ``zone0`` to ``p1`` in ``zone1``, along pv."""
        if not 0 <= p1 < zone1._point_count:
            ExecutionContext.check_point(zone1, p1)
        if not 0 <= p0 < zone0._point_count:
            ExecutionContext.check_point(zone0, p0)
        dx = zone1._current_x[p1] - zone0._current_x[p0]
        dy = zone1._current_y[p1] - zone0._current_y[p0]
        if not _INT_MIN <= dx <= _INT_MAX:
            dx = _i32(dx)
        if not _INT_MIN <= dy <= _INT_MAX:
            dy = _i32(dy)
        pv = self._pv
        r = (dx * pv._x + dy * pv._y + 0x2000) >> 14
        return r if _INT_MIN <= r <= _INT_MAX else _i32(r)

    def dual_projected_distance(self, zone1: Zone, p1: int, zone0: Zone, p0: int) -> int:
        """Original (unhinted) distance from ``p0`` to ``p1``, along the dual projection vector."""
        if not 0 <= p1 < zone1._point_count:
            ExecutionContext.check_point(zone1, p1)
        if not 0 <= p0 < zone0._point_count:
            ExecutionContext.check_point(zone0, p0)
        dx = zone1._original_x[p1] - zone0._original_x[p0]
        dy = zone1._original_y[p1] - zone0._original_y[p0]
        if not _INT_MIN <= dx <= _INT_MAX:
            dx = _i32(dx)
        if not _INT_MIN <= dy <= _INT_MAX:
            dy = _i32(dy)
        dv = self._dv
        r = (dx * dv._x + dy * dv._y + 0x2000) >> 14
        return r if _INT_MIN <= r <= _INT_MAX else _i32(r)

    @staticmethod
    def check_point(zone: Zone, point: int) -> int:
        """Validates a point number taken from the bytecode against the zone it indexes.

        Out-of-range point numbers are malformed font data, not a bug here;
        FreeType checks each one (``BOUNDS``) and so do we, so such a glyph
        falls back to its raw outline rather than failing with an index error.
        Returns ``point``.
        """
        if point < 0 or point >= zone._point_count:
            raise HintingException(
                f"point {point} out of range, zone has {zone._point_count} points"
            )
        return point

    def move_point(self, zone: Zone, point: int, distance: int) -> None:
        """Moves a point by a projected distance along the freedom vector, touching its axes.

        The displacement is ``distance * freedom / (freedom . projection)``,
        which reduces to ``distance`` when both vectors are the same axis.
        After FreeType 2.13's Direct_Move, the version the golden data comes
        from.
        """
        if point < 0 or point >= zone._point_count:
            ExecutionContext.check_point(zone, point)
        if not _INT_MIN <= distance <= _INT_MAX:
            distance = _i32(distance)
        fv = self._fv
        fx = fv._x
        fy = fv._y
        # freedom . projection, inlined from _freedom_dot_projection
        if fx == ONE_F2DOT14:
            f_dot_p = self._pv._x
        elif fy == ONE_F2DOT14:
            f_dot_p = self._pv._y
        else:
            pv = self._pv
            f_dot_p = (pv._x * fx + pv._y * fy) >> 14
        if -0x400 < f_dot_p < 0x400:
            f_dot_p = ONE_F2DOT14
        if fx != 0:
            # backward-compatibility (v40 grayscale): never grid-fit in the x direction, so
            # horizontal stems keep their natural sub-pixel position and are not darkened by
            # antialiasing
            if not self._backward_compatibility:
                # mul_div(d, f, f) == d exactly, the common axis-aligned case
                v = zone._current_x[point] + (
                    distance if fx == f_dot_p else mul_div(distance, fx, f_dot_p)
                )
                zone._current_x[point] = v if _INT_MIN <= v <= _INT_MAX else _i32(v)
            zone._touched_x[point] = True
        if fy != 0:
            # y moves are allowed until IUP has run on both axes; afterwards the glyph is frozen
            if not (self._backward_compatibility and self._iupx_called and self._iupy_called):
                v = zone._current_y[point] + (
                    distance if fy == f_dot_p else mul_div(distance, fy, f_dot_p)
                )
                zone._current_y[point] = v if _INT_MIN <= v <= _INT_MAX else _i32(v)
            zone._touched_y[point] = True

    def move_original(self, zone: Zone, point: int, distance: int) -> None:
        """Moves a point's *original* position along the freedom vector (func_move_orig).

        Nothing is touched and the backward-compatibility rules do not apply.
        Used to place twilight points.
        """
        ExecutionContext.check_point(zone, point)
        distance = _i32(distance)
        fv = self._fv
        f_dot_p = self._freedom_dot_projection()
        if fv._x != 0:
            zone._original_x[point] = _i32(
                zone._original_x[point] + mul_div(distance, fv._x, f_dot_p)
            )
        if fv._y != 0:
            zone._original_y[point] = _i32(
                zone._original_y[point] + mul_div(distance, fv._y, f_dot_p)
            )

    def _freedom_dot_projection(self) -> int:
        """The dot product of the freedom and projection vectors in F2Dot14.

        As FreeType 2.13's Compute_Funcs derives it: exactly the projection
        component when the freedom vector is an axis, otherwise truncated;
        below 0x400 in magnitude (nearly perpendicular) it is replaced by 1.0
        to avoid huge moves.
        """
        fv = self._fv
        pv = self._pv
        if fv._x == ONE_F2DOT14:
            f_dot_p = pv._x
        elif fv._y == ONE_F2DOT14:
            f_dot_p = pv._y
        else:
            f_dot_p = (pv._x * fv._x + pv._y * fv._y) >> 14
        return ONE_F2DOT14 if -0x400 < f_dot_p < 0x400 else f_dot_p

    def is_backward_compatibility(self) -> bool:
        """Returns whether v40 backward-compatibility (grayscale subpixel) rules are active."""
        return self._backward_compatibility

    def set_backward_compatibility(self, value: bool) -> None:
        """Sets whether to apply v40 backward-compatibility movement rules (glyph program only)."""
        self._backward_compatibility = value

    def get_code_range(self) -> ExecutionContext.CodeRange:
        """Returns which top-level program this context runs."""
        return self._code_range

    def set_code_range(self, value: ExecutionContext.CodeRange) -> None:
        self._code_range = value

    def set_iupx_called(self) -> None:
        """Marks IUP[x] as having run; resets each program run."""
        self._iupx_called = True

    def set_iupy_called(self) -> None:
        """Marks IUP[y] as having run; resets each program run."""
        self._iupy_called = True

    def is_iup_done(self) -> bool:
        """Returns whether IUP has run on both axes (frozen for backward compatibility)."""
        return self._iupx_called and self._iupy_called

    def is_composite(self) -> bool:
        """Returns whether the running program belongs to a composite glyph."""
        return self._composite

    def set_composite(self, value: bool) -> None:
        self._composite = value

    # --- execution cursor and call state ---------------------------------

    def get_stream(self) -> BytecodeStream | None:
        """Returns the current bytecode stream."""
        return self._stream

    def set_stream(self, stream: BytecodeStream | None) -> None:
        self._stream = stream

    def get_call_depth(self) -> int:
        """Returns the current call nesting depth."""
        return self._call_depth

    def enter_call(self) -> None:
        """Increments the call nesting depth."""
        self._call_depth += 1

    def leave_call(self) -> None:
        """Decrements the call nesting depth."""
        self._call_depth -= 1

    def is_return_from_function(self) -> bool:
        """Returns true if an ``ENDF`` asked the current function body to return."""
        return self._return_from_function

    def set_return_from_function(self, value: bool) -> None:
        self._return_from_function = value


__all__ = ["ExecutionContext"]

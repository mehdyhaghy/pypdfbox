"""Wave 1369 — PDFGraphicsStreamEngine engine-subclass dispatch.

Pins the ``process_operator`` override in ``PDFGraphicsStreamEngine``
that intercepts the path / paint / clip / image operators and routes
them through the abstract hooks (``move_to`` / ``line_to`` /
``stroke_path`` / ``fill_path`` / ``clip`` / etc.) while letting
everything else fall through to the registered-processor path via
``super().process_operator``.

Specifically tests:

- the dispatch table: every recognised operator name routes to its
  matching abstract hook;
- the fall-through to ``super().process_operator`` for non-graphics
  ops (text / colour / state) so registered processors still fire;
- the unsupported-operator default: ``ZZ`` (no handler) ends up at
  ``unsupported_operator`` rather than raising;
- the malformed-operand guard: numeric operators with too few / wrong-
  typed operands silently no-op (mirrors upstream's lenient handling
  via ``checkArrayTypesClass``).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import (
    WIND_EVEN_ODD,
    WIND_NON_ZERO,
    PDFGraphicsStreamEngine,
)
from pypdfbox.cos import (
    COSBase,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)


class _RecordingEngine(PDFGraphicsStreamEngine):
    """Concrete subclass that records every hook + unsupported-operator
    invocation in source order."""

    def __init__(self) -> None:
        super().__init__(page=None)
        self.events: list[tuple[str, tuple[Any, ...]]] = []
        self.unsupported: list[tuple[str, list[COSBase]]] = []
        self._current_point: tuple[float, float] | None = None

    # --- path-construction hooks ---

    def append_rectangle(self, p0, p1, p2, p3) -> None:  # noqa: ANN001
        self.events.append(("append_rectangle", (p0, p1, p2, p3)))
        self._current_point = p0

    def move_to(self, x: float, y: float) -> None:
        self.events.append(("move_to", (x, y)))
        self._current_point = (x, y)

    def line_to(self, x: float, y: float) -> None:
        self.events.append(("line_to", (x, y)))
        self._current_point = (x, y)

    def curve_to(self, x1, y1, x2, y2, x3, y3) -> None:  # noqa: ANN001
        self.events.append(("curve_to", (x1, y1, x2, y2, x3, y3)))
        self._current_point = (x3, y3)

    def close_path(self) -> None:
        self.events.append(("close_path", ()))

    def get_current_point(self) -> tuple[float, float] | None:
        return self._current_point

    # --- paint hooks ---

    def stroke_path(self) -> None:
        self.events.append(("stroke_path", ()))

    def fill_path(self, winding_rule: int) -> None:
        self.events.append(("fill_path", (winding_rule,)))

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        self.events.append(("fill_and_stroke_path", (winding_rule,)))

    def end_path(self) -> None:
        self.events.append(("end_path", ()))

    # --- clip ---

    def clip(self, winding_rule: int) -> None:
        self.events.append(("clip", (winding_rule,)))

    # --- shading / image ---

    def shading_fill(self, shading_name: COSName) -> None:
        self.events.append(("shading_fill", (shading_name,)))

    def draw_image(self, pd_image: Any) -> None:
        self.events.append(("draw_image", (pd_image,)))

    # --- catch-all fall-through ---

    def unsupported_operator(self, operator, operands) -> None:  # noqa: ANN001
        self.unsupported.append((operator.get_name(), list(operands)))


def _f(value: float) -> COSFloat:
    return COSFloat(value)


def _i(value: int) -> COSInteger:
    return COSInteger.get(value)


# ---------- path construction routing ----------


def test_move_to_dispatches_via_hook() -> None:
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(10.0), _f(20.0)])
    assert engine.events == [("move_to", (10.0, 20.0))]


def test_line_to_dispatches_via_hook() -> None:
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(0.0), _f(0.0)])
    engine.process_operator("l", [_f(5.0), _f(7.0)])
    assert ("line_to", (5.0, 7.0)) in engine.events


def test_curve_to_full_dispatches_six_floats() -> None:
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(0.0), _f(0.0)])
    engine.process_operator("c", [_f(1.0), _f(2.0), _f(3.0), _f(4.0), _f(5.0), _f(6.0)])
    assert ("curve_to", (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)) in engine.events


def test_curve_to_replicate_initial_point_v() -> None:
    """``v`` replicates the *initial* control point — the current path
    point at the time of dispatch."""
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(10.0), _f(20.0)])  # current = (10, 20)
    engine.process_operator("v", [_f(30.0), _f(40.0), _f(50.0), _f(60.0)])
    # First control = current; second = (30, 40); end = (50, 60).
    assert ("curve_to", (10.0, 20.0, 30.0, 40.0, 50.0, 60.0)) in engine.events


def test_curve_to_replicate_final_point_y() -> None:
    """``y`` replicates the *final* control point with the end point."""
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(0.0), _f(0.0)])
    engine.process_operator("y", [_f(1.0), _f(2.0), _f(3.0), _f(4.0)])
    assert ("curve_to", (1.0, 2.0, 3.0, 4.0, 3.0, 4.0)) in engine.events


def test_append_rect_dispatches_four_corners() -> None:
    """``re`` synthesises the four corners of the rectangle and
    forwards them to ``append_rectangle``."""
    engine = _RecordingEngine()
    engine.process_operator("re", [_f(10.0), _f(20.0), _f(30.0), _f(40.0)])
    # corners: (x, y), (x+w, y), (x+w, y+h), (x, y+h)
    assert engine.events == [
        ("append_rectangle", ((10.0, 20.0), (40.0, 20.0), (40.0, 60.0), (10.0, 60.0))),
    ]


def test_close_path_h_dispatches() -> None:
    engine = _RecordingEngine()
    # Upstream ClosePath is a no-op without an initial MoveTo (no current
    # point); open a subpath first so the close actually fires.
    engine.process_operator("m", [_f(1.0), _f(2.0)])
    engine.process_operator("h", [])
    assert engine.events == [("move_to", (1.0, 2.0)), ("close_path", ())]


def test_close_path_h_without_current_point_is_noop() -> None:
    """``h`` with no current point warn-logs and does not close (mirrors
    upstream ``ClosePath.process``'s ``getCurrentPoint() == null`` guard)."""
    engine = _RecordingEngine()
    engine.process_operator("h", [])
    assert engine.events == []


# ---------- path painting routing ----------


def test_stroke_path_S_dispatches() -> None:
    engine = _RecordingEngine()
    engine.process_operator("S", [])
    assert engine.events == [("stroke_path", ())]


def test_close_and_stroke_s_dispatches_close_then_stroke() -> None:
    engine = _RecordingEngine()
    # ``s`` routes its close through ``h`` upstream, so it only closes when
    # a subpath is open; open one first.
    engine.process_operator("m", [_f(1.0), _f(2.0)])
    engine.process_operator("s", [])
    assert engine.events == [
        ("move_to", (1.0, 2.0)),
        ("close_path", ()),
        ("stroke_path", ()),
    ]


def test_fill_path_f_uses_non_zero_winding() -> None:
    engine = _RecordingEngine()
    engine.process_operator("f", [])
    assert engine.events == [("fill_path", (WIND_NON_ZERO,))]


def test_fill_path_F_legacy_uses_non_zero_winding() -> None:
    """Legacy ``F`` operator: same effect as ``f``."""
    engine = _RecordingEngine()
    engine.process_operator("F", [])
    assert engine.events == [("fill_path", (WIND_NON_ZERO,))]


def test_fill_path_f_star_uses_even_odd() -> None:
    engine = _RecordingEngine()
    engine.process_operator("f*", [])
    assert engine.events == [("fill_path", (WIND_EVEN_ODD,))]


def test_fill_and_stroke_B_non_zero() -> None:
    engine = _RecordingEngine()
    engine.process_operator("B", [])
    assert engine.events == [("fill_and_stroke_path", (WIND_NON_ZERO,))]


def test_fill_and_stroke_B_star_even_odd() -> None:
    engine = _RecordingEngine()
    engine.process_operator("B*", [])
    assert engine.events == [("fill_and_stroke_path", (WIND_EVEN_ODD,))]


def test_close_fill_and_stroke_b_non_zero() -> None:
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(1.0), _f(2.0)])
    engine.process_operator("b", [])
    assert engine.events == [
        ("move_to", (1.0, 2.0)),
        ("close_path", ()),
        ("fill_and_stroke_path", (WIND_NON_ZERO,)),
    ]


def test_close_fill_and_stroke_b_star_even_odd() -> None:
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(1.0), _f(2.0)])
    engine.process_operator("b*", [])
    assert engine.events == [
        ("move_to", (1.0, 2.0)),
        ("close_path", ()),
        ("fill_and_stroke_path", (WIND_EVEN_ODD,)),
    ]


def test_end_path_n_dispatches() -> None:
    engine = _RecordingEngine()
    engine.process_operator("n", [])
    assert engine.events == [("end_path", ())]


# ---------- clipping ----------


def test_clip_W_non_zero_winding() -> None:
    engine = _RecordingEngine()
    engine.process_operator("W", [])
    assert engine.events == [("clip", (WIND_NON_ZERO,))]


def test_clip_W_star_even_odd() -> None:
    engine = _RecordingEngine()
    engine.process_operator("W*", [])
    assert engine.events == [("clip", (WIND_EVEN_ODD,))]


# ---------- shading ----------


def test_shading_fill_sh_dispatches_with_name_operand() -> None:
    engine = _RecordingEngine()
    name = COSName.get_pdf_name("Sh1")
    engine.process_operator("sh", [name])
    assert engine.events == [("shading_fill", (name,))]


def test_shading_fill_sh_no_name_operand_silently_skipped() -> None:
    """No name operand → engine silently skips (matches upstream's
    defensive handling — ``shading_fill`` is never invoked with a
    non-name operand)."""
    engine = _RecordingEngine()
    engine.process_operator("sh", [])
    assert engine.events == []


def test_shading_fill_non_name_operand_silently_skipped() -> None:
    engine = _RecordingEngine()
    engine.process_operator("sh", [COSString(b"oops")])
    assert engine.events == []


# ---------- malformed-operand guards (silent no-op) ----------


def test_move_to_with_missing_operand_silently_skipped() -> None:
    """Only one operand instead of two → no ``move_to`` dispatched."""
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(10.0)])
    assert engine.events == []


def test_move_to_with_non_numeric_operand_silently_skipped() -> None:
    """Mirrors upstream ``checkArrayTypesClass``-style leniency."""
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(10.0), COSString(b"oops")])
    assert engine.events == []


def test_curve_to_with_short_operand_list_skipped() -> None:
    """``c`` needs 6 operands; 5 is short → silent skip."""
    engine = _RecordingEngine()
    engine.process_operator("c", [_f(1.0), _f(2.0), _f(3.0), _f(4.0), _f(5.0)])
    assert engine.events == []


def test_v_without_current_point_falls_back_to_move_to() -> None:
    """``v`` replicates the current point as its first control point. When
    no subpath is open (``get_current_point`` is ``None``) upstream
    ``CurveToReplicateInitialPoint`` warn-logs and falls back to
    ``moveTo(x3, y3)`` — the endpoint — rather than a silent skip."""
    engine = _RecordingEngine()  # no preceding move_to
    engine.process_operator("v", [_f(1.0), _f(2.0), _f(3.0), _f(4.0)])
    # x3, y3 = operands[2], operands[3] = (3.0, 4.0)
    assert engine.events == [("move_to", (3.0, 4.0))]


def test_v_with_current_point_dispatches_curve() -> None:
    """With a subpath open, ``v`` uses the current point as the first
    control point and dispatches ``curve_to``."""
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(10.0), _f(20.0)])
    engine.process_operator("v", [_f(1.0), _f(2.0), _f(3.0), _f(4.0)])
    assert engine.events == [
        ("move_to", (10.0, 20.0)),
        ("curve_to", (10.0, 20.0, 1.0, 2.0, 3.0, 4.0)),
    ]


# ---------- unsupported (unknown operator) ----------


def test_unknown_operator_falls_to_unsupported_via_super() -> None:
    """A name with no graphics-engine handler *and* no registered lite
    stub falls through to ``unsupported_operator``. The graphics
    engine's ``process_operator`` override ends with ``super().process_operator``
    which routes unknowns through the base engine's
    ``unsupported_operator`` hook."""
    engine = _RecordingEngine()
    engine.process_operator("ZZ", [_i(1)])
    assert engine.unsupported == [("ZZ", [_i(1)])]


# ---------- super-route: q / Q / cm flow through the standard processor path ----------


def test_save_graphics_state_q_routes_through_engine_hook() -> None:
    """``q`` triggers the engine's ``save_graphics_state`` hook and ``Q`` the
    ``restore_graphics_state`` hook — but ``Q`` only pops when the graphics
    stack has more than one frame (the registered ``Restore`` operator's
    ``get_graphics_stack_size() > 1`` guard; PDFBOX-161). The graphics engine
    dispatches ``q`` / ``Q`` through the inherited ``Save`` / ``Restore``
    processors (NOT inline), so the guard applies. We model a depth counter
    seeded at 1 so the matched ``Q`` has a frame to pop."""

    class _Capture(_RecordingEngine):
        def __init__(self) -> None:
            super().__init__()
            self.saves = 0
            self.restores = 0
            self._depth = 1

        def save_graphics_state(self) -> None:
            self.saves += 1
            self._depth += 1

        def restore_graphics_state(self) -> None:
            self.restores += 1
            self._depth -= 1

        def get_graphics_stack_size(self) -> int:
            return self._depth

    engine = _Capture()
    engine.process_operator("q", [])
    engine.process_operator("Q", [])
    assert engine.saves == 1
    assert engine.restores == 1


def test_unbalanced_Q_does_not_underflow_via_graphics_engine() -> None:
    """An extra ``Q`` (empty stack) routed through the graphics engine raises
    the registered ``Restore`` operator's EmptyGraphicsStackException, which
    ``operator_exception`` swallows — the ``restore_graphics_state`` hook is
    NOT called, so the depth never under-flows below the seed frame. Regression
    guard for the wave-1545 fix (inline ``Q`` used to bypass the guard)."""

    class _Capture(_RecordingEngine):
        def __init__(self) -> None:
            super().__init__()
            self.restores = 0
            self._depth = 1

        def restore_graphics_state(self) -> None:
            self.restores += 1
            self._depth -= 1

        def get_graphics_stack_size(self) -> int:
            return self._depth

    engine = _Capture()
    engine.process_operator("Q", [])  # empty stack -> swallowed, no pop
    assert engine.restores == 0
    assert engine.get_graphics_stack_size() == 1


def test_str_form_of_process_operator_works_for_path_ops() -> None:
    """The ``str`` overload of ``process_operator`` accepts a bare
    operator name and re-routes through ``Operator.get_operator`` —
    pinning the parity overload from upstream."""
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(1.0), _f(2.0)])
    assert engine.events == [("move_to", (1.0, 2.0))]


# ---------- transformed_point default is identity ----------


def test_transformed_point_default_is_identity() -> None:
    """No graphics-state stack on the base graphics engine → the
    transform is the identity, so path coordinates flow through
    unchanged."""
    engine = _RecordingEngine()
    engine.process_operator("m", [_f(3.5), _f(4.5)])
    # Identity transform: passed through verbatim.
    assert engine.events == [("move_to", (3.5, 4.5))]


def test_transformed_point_override_applies_to_path_ops() -> None:
    """A subclass that overrides ``transformed_point`` (e.g. to apply
    the CTM) has its transform applied to every path-constructor
    coordinate, matching upstream's per-operator transform step."""

    class _Scaling(_RecordingEngine):
        def transformed_point(self, x: float, y: float) -> tuple[float, float]:
            return (x * 2, y * 2)

    engine = _Scaling()
    engine.process_operator("m", [_f(3.0), _f(4.0)])
    assert engine.events == [("move_to", (6.0, 8.0))]

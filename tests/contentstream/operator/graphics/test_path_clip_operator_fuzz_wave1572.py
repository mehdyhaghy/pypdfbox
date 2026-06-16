"""Fuzz / parity tests for path-construction, path-painting and clipping
operators — wave 1572 (Agent B).

Two surfaces are hammered:

1. The lite operator-validation stubs in
   ``pypdfbox.contentstream.operator.graphics`` and
   ``pypdfbox.contentstream.operator.path`` — operand-count / operand-type
   guards that mirror upstream PDFBox ``process`` methods
   (``MissingOperandException`` on too-few operands;
   ``checkArrayTypesClass(operands, COSNumber.class)`` whole-list type guard).

2. The semantic path-construction / painting / clipping dispatch in
   :class:`PDFGraphicsStreamEngine.process_operator` — the abstract hooks
   (``move_to`` / ``line_to`` / ``curve_to`` / ``append_rectangle`` /
   ``close_path`` / ``stroke_path`` / ``fill_path`` / ``fill_and_stroke_path``
   / ``end_path`` / ``clip``) are recorded by a test subclass and the
   recorded sequence is compared to what upstream PDFBox would emit:

   * ``m`` sets the current point + starts a subpath; ``l`` / ``c`` append.
   * ``re`` appends a closed 4-corner subpath with the upstream corner
     winding ``(x,y) (x+w,y) (x+w,y+h) (x,y+h)``.
   * ``v`` (first control point = current point) vs ``y`` (second control
     point = endpoint) curve-replicate variants map their operands to the
     right ``curve_to`` arguments.
   * painting ops (``S`` / ``s`` / ``f`` / ``f*`` / ``B`` / ``B*`` / ``b`` /
     ``b*`` / ``n``) invoke the right hook with the right winding rule.
   * ``W`` / ``W*`` defer the clip: the clip hook fires on the SAME
     ``process_operator`` call, but upstream applies the intersection only
     when the following painting / ``n`` operator runs — we assert the clip
     hook ordering (clip recorded BEFORE the painting hook that consumes it).
   * ``n`` with a pending clip paints nothing (only ``end_path`` + ``clip``).
   * missing operands raise; odd / trailing operands follow the upstream
     leniency rules.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import Operator
from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.graphics.append_rectangle_to_path import (
    AppendRectangleToPath,
)
from pypdfbox.contentstream.operator.path.curve_to import CurveTo
from pypdfbox.contentstream.operator.path.curve_to_replicate_final_point import (
    CurveToReplicateFinalPoint,
)
from pypdfbox.contentstream.operator.path.curve_to_replicate_initial_point import (
    CurveToReplicateInitialPoint,
)
from pypdfbox.contentstream.operator.path.line_to import LineTo
from pypdfbox.contentstream.operator.path.move_to import MoveTo
from pypdfbox.contentstream.pdf_graphics_stream_engine import (
    WIND_EVEN_ODD,
    WIND_NON_ZERO,
    PDFGraphicsStreamEngine,
)
from pypdfbox.cos import COSBase, COSFloat, COSInteger, COSName


# --------------------------------------------------------------------------
# Recording engine — captures the abstract-hook call sequence so the test can
# assert on the semantic events upstream PDFBox would dispatch.
# --------------------------------------------------------------------------
class RecordingEngine(PDFGraphicsStreamEngine):
    def __init__(self) -> None:
        super().__init__(page=None)
        self.events: list[tuple] = []
        self._current: tuple[float, float] | None = None

    # path construction
    def move_to(self, x: float, y: float) -> None:
        self.events.append(("move_to", x, y))
        self._current = (x, y)

    def line_to(self, x: float, y: float) -> None:
        self.events.append(("line_to", x, y))
        self._current = (x, y)

    def curve_to(
        self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float
    ) -> None:
        self.events.append(("curve_to", x1, y1, x2, y2, x3, y3))
        self._current = (x3, y3)

    def append_rectangle(self, p0, p1, p2, p3) -> None:
        self.events.append(("append_rectangle", p0, p1, p2, p3))
        # upstream: the rectangle leaves the current point at p0
        self._current = p0

    def close_path(self) -> None:
        self.events.append(("close_path",))

    def get_current_point(self):
        return self._current

    # painting
    def stroke_path(self) -> None:
        self.events.append(("stroke_path",))
        self._current = None

    def fill_path(self, winding_rule: int) -> None:
        self.events.append(("fill_path", winding_rule))
        self._current = None

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        self.events.append(("fill_and_stroke_path", winding_rule))
        self._current = None

    def end_path(self) -> None:
        self.events.append(("end_path",))
        self._current = None

    def clip(self, winding_rule: int) -> None:
        self.events.append(("clip", winding_rule))

    def shading_fill(self, shading_name: COSName) -> None:
        self.events.append(("shading_fill", shading_name))


def _n(v: float) -> COSFloat:
    return COSFloat(v)


def _run(engine: RecordingEngine, name: str, operands: list[COSBase]) -> None:
    engine.process_operator(Operator.get_operator(name), operands)


# ==========================================================================
# Path construction: current point + subpath building
# ==========================================================================
def test_move_to_sets_current_point_and_starts_subpath() -> None:
    e = RecordingEngine()
    _run(e, "m", [_n(10.0), _n(20.0)])
    assert e.events == [("move_to", 10.0, 20.0)]
    assert e.get_current_point() == (10.0, 20.0)


def test_line_to_appends_after_move() -> None:
    e = RecordingEngine()
    _run(e, "m", [_n(0.0), _n(0.0)])
    _run(e, "l", [_n(5.0), _n(7.0)])
    assert e.events[-1] == ("line_to", 5.0, 7.0)
    assert e.get_current_point() == (5.0, 7.0)


def test_line_to_without_move_falls_back_to_move() -> None:
    # upstream LineTo warn-logs + moveTo when there is no current point.
    e = RecordingEngine()
    _run(e, "l", [_n(3.0), _n(4.0)])
    assert e.events == [("move_to", 3.0, 4.0)]


def test_curve_to_without_move_falls_back_to_move_to_endpoint() -> None:
    e = RecordingEngine()
    _run(e, "c", [_n(1), _n(2), _n(3), _n(4), _n(5), _n(6)])
    # falls back to moveTo(x3, y3)
    assert e.events == [("move_to", 5.0, 6.0)]


def test_curve_to_appends_with_two_control_points() -> None:
    e = RecordingEngine()
    _run(e, "m", [_n(0), _n(0)])
    _run(e, "c", [_n(1), _n(2), _n(3), _n(4), _n(5), _n(6)])
    assert e.events[-1] == ("curve_to", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    assert e.get_current_point() == (5.0, 6.0)


# ==========================================================================
# re — closed 4-corner subpath, upstream corner winding
# ==========================================================================
def test_append_rectangle_corner_winding() -> None:
    e = RecordingEngine()
    _run(e, "re", [_n(1.0), _n(2.0), _n(10.0), _n(20.0)])
    assert len(e.events) == 1
    kind, p0, p1, p2, p3 = e.events[0]
    assert kind == "append_rectangle"
    # x,y / x+w,y / x+w,y+h / x,y+h  (counter-clockwise from lower-left)
    assert p0 == (1.0, 2.0)
    assert p1 == (11.0, 2.0)
    assert p2 == (11.0, 22.0)
    assert p3 == (1.0, 22.0)


def test_append_rectangle_negative_dimensions() -> None:
    e = RecordingEngine()
    _run(e, "re", [_n(5.0), _n(5.0), _n(-3.0), _n(-4.0)])
    _, p0, p1, p2, p3 = e.events[0]
    assert p0 == (5.0, 5.0)
    assert p1 == (2.0, 5.0)
    assert p2 == (2.0, 1.0)
    assert p3 == (5.0, 1.0)


# ==========================================================================
# v vs y curve-replicate variants
# ==========================================================================
def test_v_first_control_is_current_point() -> None:
    # v x2 y2 x3 y3 -> curve_to(current, current, x2, y2, x3, y3)
    e = RecordingEngine()
    _run(e, "m", [_n(100.0), _n(200.0)])
    _run(e, "v", [_n(3.0), _n(4.0), _n(5.0), _n(6.0)])
    assert e.events[-1] == (
        "curve_to",
        100.0,
        200.0,  # first control = current point
        3.0,
        4.0,  # second control = (x2, y2)
        5.0,
        6.0,  # endpoint = (x3, y3)
    )
    assert e.get_current_point() == (5.0, 6.0)


def test_y_second_control_is_endpoint() -> None:
    # y x1 y1 x3 y3 -> curve_to(x1, y1, x3, y3, x3, y3)
    e = RecordingEngine()
    _run(e, "m", [_n(0.0), _n(0.0)])
    _run(e, "y", [_n(1.0), _n(2.0), _n(9.0), _n(8.0)])
    assert e.events[-1] == (
        "curve_to",
        1.0,
        2.0,  # first control = (x1, y1)
        9.0,
        8.0,  # second control = endpoint
        9.0,
        8.0,  # endpoint
    )
    assert e.get_current_point() == (9.0, 8.0)


def test_v_without_move_falls_back_to_move_to_endpoint() -> None:
    e = RecordingEngine()
    _run(e, "v", [_n(3.0), _n(4.0), _n(5.0), _n(6.0)])
    assert e.events == [("move_to", 5.0, 6.0)]


def test_y_without_move_falls_back_to_move_to_endpoint() -> None:
    e = RecordingEngine()
    _run(e, "y", [_n(1.0), _n(2.0), _n(9.0), _n(8.0)])
    assert e.events == [("move_to", 9.0, 8.0)]


# ==========================================================================
# h — close path
# ==========================================================================
def test_close_path_emits_close() -> None:
    e = RecordingEngine()
    _run(e, "m", [_n(0), _n(0)])
    _run(e, "l", [_n(10), _n(0)])
    _run(e, "h", [])
    assert e.events[-1] == ("close_path",)


def test_close_path_without_current_point_is_noop() -> None:
    # upstream ClosePath warn-logs + returns when there is no current point.
    e = RecordingEngine()
    _run(e, "h", [])
    assert e.events == []


# ==========================================================================
# Painting operators consume + reset the path
# ==========================================================================
@pytest.mark.parametrize(
    ("op_name", "expected"),
    [
        ("S", ("stroke_path",)),
        ("f", ("fill_path", WIND_NON_ZERO)),
        ("F", ("fill_path", WIND_NON_ZERO)),
        ("f*", ("fill_path", WIND_EVEN_ODD)),
        ("B", ("fill_and_stroke_path", WIND_NON_ZERO)),
        ("B*", ("fill_and_stroke_path", WIND_EVEN_ODD)),
        ("n", ("end_path",)),
    ],
    ids=["S", "f", "F", "f_star", "B", "B_star", "n"],
)
def test_painting_op_dispatch(op_name: str, expected: tuple) -> None:
    e = RecordingEngine()
    _run(e, "m", [_n(0), _n(0)])
    _run(e, "l", [_n(1), _n(1)])
    _run(e, op_name, [])
    assert e.events[-1] == expected
    # path is reset after painting
    assert e.get_current_point() is None


def test_close_and_stroke_closes_then_strokes() -> None:
    # s = h then S
    e = RecordingEngine()
    _run(e, "m", [_n(0), _n(0)])
    _run(e, "l", [_n(1), _n(1)])
    _run(e, "s", [])
    assert e.events[-2:] == [("close_path",), ("stroke_path",)]


def test_close_fill_non_zero_and_stroke() -> None:
    # b = h then B (non-zero)
    e = RecordingEngine()
    _run(e, "m", [_n(0), _n(0)])
    _run(e, "l", [_n(1), _n(1)])
    _run(e, "b", [])
    assert e.events[-2:] == [
        ("close_path",),
        ("fill_and_stroke_path", WIND_NON_ZERO),
    ]


def test_close_fill_even_odd_and_stroke() -> None:
    # b* = h then B* (even-odd)
    e = RecordingEngine()
    _run(e, "m", [_n(0), _n(0)])
    _run(e, "l", [_n(1), _n(1)])
    _run(e, "b*", [])
    assert e.events[-2:] == [
        ("close_path",),
        ("fill_and_stroke_path", WIND_EVEN_ODD),
    ]


# ==========================================================================
# W / W* — deferred clip applied at the next painting op
# ==========================================================================
def test_clip_non_zero_then_fill_orders_clip_before_paint() -> None:
    e = RecordingEngine()
    _run(e, "re", [_n(0), _n(0), _n(10), _n(10)])
    _run(e, "W", [])
    _run(e, "n", [])
    # clip hook fires, then end_path; the clip is for the next painting op.
    assert ("clip", WIND_NON_ZERO) in e.events
    clip_idx = e.events.index(("clip", WIND_NON_ZERO))
    end_idx = e.events.index(("end_path",))
    assert clip_idx < end_idx


def test_clip_even_odd_winding_rule() -> None:
    e = RecordingEngine()
    _run(e, "re", [_n(0), _n(0), _n(10), _n(10)])
    _run(e, "W*", [])
    _run(e, "n", [])
    assert ("clip", WIND_EVEN_ODD) in e.events


def test_clip_then_stroke_paints_and_clips() -> None:
    e = RecordingEngine()
    _run(e, "m", [_n(0), _n(0)])
    _run(e, "l", [_n(5), _n(5)])
    _run(e, "W", [])
    _run(e, "S", [])
    assert ("clip", WIND_NON_ZERO) in e.events
    assert ("stroke_path",) in e.events


def test_n_with_pending_clip_paints_nothing() -> None:
    e = RecordingEngine()
    _run(e, "re", [_n(0), _n(0), _n(10), _n(10)])
    _run(e, "W", [])
    _run(e, "n", [])
    paint_events = [
        ev[0]
        for ev in e.events
        if ev[0] in ("stroke_path", "fill_path", "fill_and_stroke_path")
    ]
    assert paint_events == []
    assert ("end_path",) in e.events


# ==========================================================================
# Shading fill — sh requires a name operand
# ==========================================================================
def test_shading_fill_with_name() -> None:
    e = RecordingEngine()
    _run(e, "sh", [COSName.get_pdf_name("Sh0")])
    assert e.events == [("shading_fill", COSName.get_pdf_name("Sh0"))]


def test_shading_fill_without_name_is_noop() -> None:
    e = RecordingEngine()
    _run(e, "sh", [])
    assert e.events == []


# ==========================================================================
# Missing-operand handling through the engine (lenient: logged + swallowed)
# ==========================================================================
@pytest.mark.parametrize(
    ("op_name", "operands"),
    [
        ("m", [_n(1.0)]),
        ("l", [_n(1.0)]),
        ("c", [_n(1), _n(2), _n(3), _n(4), _n(5)]),
        ("v", [_n(1), _n(2), _n(3)]),
        ("y", [_n(1), _n(2), _n(3)]),
        ("re", [_n(1), _n(2), _n(3)]),
    ],
    ids=["m", "l", "c", "v", "y", "re"],
)
def test_engine_missing_operands_are_swallowed(
    op_name: str, operands: list[COSBase]
) -> None:
    # PDFGraphicsStreamEngine wraps the MissingOperandException in
    # operator_exception (lenient) — no exception escapes, no hook fires.
    e = RecordingEngine()
    _run(e, op_name, operands)
    assert e.events == []


# ==========================================================================
# Lite operator stubs — operand validation matches upstream
# ==========================================================================
def test_move_to_stub_missing_operand_raises() -> None:
    with pytest.raises(MissingOperandException):
        MoveTo().process(Operator.get_operator("m"), [_n(1.0)])


def test_move_to_stub_non_number_silent_skip() -> None:
    # only the two consumed operands are type-checked for m.
    MoveTo().process(
        Operator.get_operator("m"), [COSName.get_pdf_name("x"), _n(1.0)]
    )


def test_line_to_stub_missing_operand_raises() -> None:
    with pytest.raises(MissingOperandException):
        LineTo().process(Operator.get_operator("l"), [])


def test_curve_to_stub_missing_operand_raises() -> None:
    with pytest.raises(MissingOperandException):
        CurveTo().process(
            Operator.get_operator("c"), [_n(1), _n(2), _n(3)]
        )


def test_curve_to_stub_whole_list_type_guard() -> None:
    # upstream checkArrayTypesClass(operands, COSNumber.class) over WHOLE list:
    # a trailing non-number makes it a silent no-op.
    CurveTo().process(
        Operator.get_operator("c"),
        [_n(1), _n(2), _n(3), _n(4), _n(5), _n(6), COSName.get_pdf_name("z")],
    )


def test_v_stub_missing_operand_raises() -> None:
    with pytest.raises(MissingOperandException):
        CurveToReplicateInitialPoint().process(
            Operator.get_operator("v"), [_n(1), _n(2), _n(3)]
        )


def test_y_stub_missing_operand_raises() -> None:
    with pytest.raises(MissingOperandException):
        CurveToReplicateFinalPoint().process(
            Operator.get_operator("y"), [_n(1), _n(2)]
        )


def test_append_rectangle_stub_missing_operand_raises() -> None:
    with pytest.raises(MissingOperandException):
        AppendRectangleToPath().process(
            Operator.get_operator("re"), [_n(1), _n(2), _n(3)]
        )


def test_append_rectangle_stub_trailing_non_number_silent_skip() -> None:
    # Regression for wave 1572 fix: upstream AppendRectangleToPath calls
    # checkArrayTypesClass(operands, COSNumber.class) over the WHOLE operand
    # list — a trailing non-number (x y w h /Name re) is a silent no-op, not
    # an ignored trailing token. Returns without raising.
    AppendRectangleToPath().process(
        Operator.get_operator("re"),
        [_n(1), _n(2), _n(3), _n(4), COSName.get_pdf_name("trailing")],
    )


def test_append_rectangle_stub_integer_operands_accepted() -> None:
    AppendRectangleToPath().process(
        Operator.get_operator("re"),
        [COSInteger.get(0), COSInteger.get(0), COSInteger.get(9),
         COSInteger.get(9)],
    )

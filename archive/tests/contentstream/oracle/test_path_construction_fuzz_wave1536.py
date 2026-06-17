"""Differential operand / current-point fuzz of the PATH-CONSTRUCTION and
PATH-PAINTING content-stream operator processors vs Apache PDFBox 3.0.7
(wave 1536).

Surface: the gatekeeping + state interaction of the path operators driven by
:class:`PDFGraphicsStreamEngine.process_operator` —

* construction — ``m`` (MoveTo), ``l`` (LineTo), ``c`` (CurveTo), ``v``
  (CurveToReplicateInitialPoint), ``y`` (CurveToReplicateFinalPoint), ``re``
  (AppendRectangleToPath), ``h`` (ClosePath): fixed COSNumber arity, the
  per-operand vs whole-list type guard, and the current-point fallbacks;
* painting — ``S`` ``s`` ``f`` ``F`` ``f*`` ``B`` ``B*`` ``b`` ``b*`` ``n``:
  zero operands, current-path / current-point state interaction, trailing
  operand tolerance.

How the oracle works
--------------------
``oracle/probes/PathConstructionFuzzProbe.java`` instantiates each upstream
``...operator.graphics.*`` processor with a recording
:class:`PDFGraphicsStreamEngine` subclass (a nullable current point + a
hook trace) and calls its ``process(Operator, List)`` DIRECTLY — routing
through a stream would swallow the arity/type exception. It overrides
``transformedPoint`` to an identity transform so the path hooks fire without
an active graphics-state stack. For each case it emits::

    <id>\\tERR:<SimpleExceptionName>      # process() threw
    <id>\\t<trace>|cp=<point-or-none>     # process() ran (trace = fired hooks)

The pypdfbox side replays the IDENTICAL operand lists through the SAME
canonical engine dispatch (``PDFGraphicsStreamEngine.process_operator``) on an
equivalent recording engine, and emits the same projection.

Real bugs this wave caught
--------------------------
1. ``l`` / ``c`` (LineTo / CurveTo) without an initial MoveTo: pypdfbox called
   ``line_to`` / ``curve_to`` with no current point, while upstream warn-logs
   and falls back to ``move_to`` (``move_to(x3, y3)`` for ``c``). Fixed in
   ``process_operator``; ``l_two_nocp`` / ``c_six_nocp`` pin it.
2. ``v`` (CurveToReplicateInitialPoint) without an initial MoveTo: pypdfbox
   silently skipped (``if current is None: return``) while upstream falls back
   to ``move_to(x3, y3)``. Fixed; ``v_four_nocp`` pins it.
3. ``y`` (CurveToReplicateFinalPoint) without an initial MoveTo: pypdfbox
   unconditionally called ``curve_to`` while upstream falls back to
   ``move_to(x3, y3)``. Fixed; ``y_four_nocp`` pins it.
4. ``h`` (ClosePath) with no current point: pypdfbox called ``close_path``
   unconditionally while upstream warn-logs + returns without closing. Fixed
   via ``_close_path_if_open``; ``h_nocp`` pins it. The close step of ``s`` /
   ``b`` / ``b*`` (which route through ``h`` upstream) inherits the guard.
5. ``c`` / ``v`` / ``y`` / ``re`` whole-list type guard: pypdfbox's
   ``_coerce_floats`` checked only the consumed window, while upstream calls
   ``checkArrayTypesClass(operands, COSNumber.class)`` over the WHOLE operand
   list — a trailing non-number (``x y w h /Name re``) is a silent no-op.
   Fixed; ``c_seven_trailing_name`` / ``v_five_trailing_null`` /
   ``y_five_trailing_name`` / ``re_five_trailing_name`` pin it. ``m`` / ``l``
   do NOT use this guard (they cast operands 0/1 individually), so
   ``m_three_trailing_name`` stays a ``move`` — that asymmetry is upstream.

No unalignable divergences were found on this surface.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.pdf_graphics_stream_engine import (
    PDFGraphicsStreamEngine,
)
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from tests.oracle.harness import requires_oracle, run_probe_text


class _Recorder(PDFGraphicsStreamEngine):
    """Recording graphics engine mirroring the Java probe's ``Recorder``: a
    nullable current point plus a ``>``-joined trace of fired path hooks."""

    def __init__(self) -> None:
        super().__init__(None)
        self._current: tuple[float, float] | None = None
        self._trace: list[str] = []

    def reset(self) -> None:
        self._current = None
        self._trace = []

    def seed_move(self) -> None:
        self._current = (10.0, 20.0)

    def _mark(self, hook: str) -> None:
        self._trace.append(hook)

    # construction hooks ------------------------------------------------------
    def move_to(self, x: float, y: float) -> None:
        self._mark("move")
        self._current = (x, y)

    def line_to(self, x: float, y: float) -> None:
        self._mark("line")
        self._current = (x, y)

    def curve_to(
        self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float
    ) -> None:
        self._mark("curve")
        self._current = (x3, y3)

    def append_rectangle(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
    ) -> None:
        self._mark("rect")
        self._current = (p0[0], p0[1])

    def get_current_point(self) -> tuple[float, float] | None:
        return self._current

    def close_path(self) -> None:
        self._mark("close")

    def end_path(self) -> None:
        self._mark("endpath")
        self._current = None

    # painting hooks ----------------------------------------------------------
    def stroke_path(self) -> None:
        self._mark("stroke")
        self._current = None

    def fill_path(self, winding_rule: int) -> None:
        self._mark("fill")
        self._current = None

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        self._mark("fillstroke")
        self._current = None

    def clip(self, winding_rule: int) -> None:
        self._mark("clip")

    def shading_fill(self, shading_name: COSName) -> None:
        self._mark("shading")

    def draw_image(self, pd_image: object) -> None:
        self._mark("image")

    # projection --------------------------------------------------------------
    def fingerprint(self) -> str:
        trace = ">".join(self._trace)
        cp = (
            "none"
            if self._current is None
            else f"{self._current[0]:.3f},{self._current[1]:.3f}"
        )
        return f"{trace}|cp={cp}"


# --- reusable operands (mirror the Java probe one-for-one) -----------------
_NUM = COSFloat(1.5)
_NUM2 = COSFloat(3.25)
_NEG = COSFloat(-4.0)
_HUGE = COSFloat(131072.0)
_INT = COSInteger.get(2)
_NAME = COSName.get_pdf_name("X")
_STR = COSString("z")
_NULL = COSNull.NULL
_ARR = COSArray()


def _ops(*items: COSBase) -> list[COSBase]:
    return list(items)


# Each entry: (id, op-name, seed-current-point?, operands).
_CASES: list[tuple[str, str, bool, list[COSBase]]] = [
    # m (MoveTo)
    ("m_empty", "m", False, _ops()),
    ("m_one", "m", False, _ops(_NUM)),
    ("m_two", "m", False, _ops(_NUM, _NUM2)),
    ("m_two_int", "m", False, _ops(_INT, _INT)),
    ("m_first_name", "m", False, _ops(_NAME, _NUM)),
    ("m_second_str", "m", False, _ops(_NUM, _STR)),
    ("m_two_neg", "m", False, _ops(_NEG, _NEG)),
    ("m_two_huge", "m", False, _ops(_HUGE, _HUGE)),
    ("m_three_trailing_name", "m", False, _ops(_NUM, _NUM2, _NAME)),
    ("m_three_trailing_num", "m", False, _ops(_NUM, _NUM2, _INT)),
    # l (LineTo)
    ("l_empty", "l", False, _ops()),
    ("l_one", "l", False, _ops(_NUM)),
    ("l_two_nocp", "l", False, _ops(_NUM, _NUM2)),
    ("l_two_cp", "l", True, _ops(_NUM, _NUM2)),
    ("l_first_name_nocp", "l", False, _ops(_NAME, _NUM)),
    ("l_first_name_cp", "l", True, _ops(_NAME, _NUM)),
    ("l_three_trailing_name_nocp", "l", False, _ops(_NUM, _NUM2, _NAME)),
    # c (CurveTo)
    ("c_empty", "c", False, _ops()),
    ("c_five", "c", False, _ops(_NUM, _NUM, _NUM, _NUM, _NUM)),
    ("c_six_nocp", "c", False, _ops(_NUM, _NUM2, _NUM, _NUM2, _NUM, _NUM2)),
    ("c_six_cp", "c", True, _ops(_NUM, _NUM2, _NUM, _NUM2, _NUM, _NUM2)),
    ("c_six_one_str", "c", True, _ops(_NUM, _NUM2, _STR, _NUM2, _NUM, _NUM2)),
    ("c_six_one_null", "c", True, _ops(_NUM, _NUM2, _NUM, _NULL, _NUM, _NUM2)),
    (
        "c_seven_trailing_name",
        "c",
        True,
        _ops(_NUM, _NUM2, _NUM, _NUM2, _NUM, _NUM2, _NAME),
    ),
    # v (CurveToReplicateInitialPoint)
    ("v_empty", "v", False, _ops()),
    ("v_three", "v", False, _ops(_NUM, _NUM, _NUM)),
    ("v_four_nocp", "v", False, _ops(_NUM, _NUM2, _NUM, _NUM2)),
    ("v_four_cp", "v", True, _ops(_NUM, _NUM2, _NUM, _NUM2)),
    ("v_four_one_name", "v", True, _ops(_NUM, _NAME, _NUM, _NUM2)),
    ("v_five_trailing_null", "v", True, _ops(_NUM, _NUM2, _NUM, _NUM2, _NULL)),
    # y (CurveToReplicateFinalPoint)
    ("y_empty", "y", False, _ops()),
    ("y_three", "y", False, _ops(_NUM, _NUM, _NUM)),
    ("y_four_nocp", "y", False, _ops(_NUM, _NUM2, _NUM, _NUM2)),
    ("y_four_cp", "y", True, _ops(_NUM, _NUM2, _NUM, _NUM2)),
    ("y_four_one_str", "y", True, _ops(_NUM, _NUM2, _STR, _NUM2)),
    ("y_five_trailing_name", "y", True, _ops(_NUM, _NUM2, _NUM, _NUM2, _NAME)),
    # re (AppendRectangleToPath)
    ("re_empty", "re", False, _ops()),
    ("re_three", "re", False, _ops(_NUM, _NUM, _NUM)),
    ("re_four", "re", False, _ops(_INT, _INT, _INT, _INT)),
    ("re_four_neg", "re", False, _ops(_NEG, _NEG, _NUM, _NUM)),
    ("re_four_one_name", "re", False, _ops(_NUM, _NAME, _NUM, _NUM)),
    ("re_four_one_arr", "re", False, _ops(_NUM, _NUM, _ARR, _NUM)),
    ("re_five_trailing_name", "re", False, _ops(_NUM, _NUM, _NUM, _NUM, _NAME)),
    # h (ClosePath)
    ("h_nocp", "h", False, _ops()),
    ("h_cp", "h", True, _ops()),
    ("h_cp_extra", "h", True, _ops(_NUM)),
    # painting
    ("S_nocp", "S", False, _ops()),
    ("S_cp", "S", True, _ops()),
    ("S_cp_extra", "S", True, _ops(_NUM)),
    ("s_nocp", "s", False, _ops()),
    ("s_cp", "s", True, _ops()),
    ("f_nocp", "f", False, _ops()),
    ("f_cp", "f", True, _ops()),
    ("F_cp", "F", True, _ops()),
    ("fstar_cp", "f*", True, _ops()),
    ("B_cp", "B", True, _ops()),
    ("Bstar_cp", "B*", True, _ops()),
    ("b_nocp", "b", False, _ops()),
    ("b_cp", "b", True, _ops()),
    ("bstar_cp", "b*", True, _ops()),
    ("n_nocp", "n", False, _ops()),
    ("n_cp", "n", True, _ops()),
    ("n_cp_extra", "n", True, _ops(_NUM)),
]

_IDS = [c[0] for c in _CASES]


def _pypdfbox_outcomes() -> dict[str, str]:
    eng = _Recorder()
    out: dict[str, str] = {}
    for case_id, op_name, seed, operands in _CASES:
        eng.reset()
        if seed:
            eng.seed_move()
        try:
            # Call the raising path-op dispatch directly (the pypdfbox
            # equivalent of the Java probe's ``processor.process(...)``):
            # ``process_operator`` itself would funnel a
            # MissingOperandException into ``operator_exception`` (the
            # upstream lenient stream-level error policy), hiding the
            # arity contract this probe asserts on.
            eng._process_path_operator(
                op_name, Operator.get_operator(op_name), operands
            )
        except OSError as exc:
            out[case_id] = f"ERR:{_err_name(exc)}"
            continue
        out[case_id] = eng.fingerprint()
    return out


def _err_name(exc: Exception) -> str:
    """Map the pypdfbox exception class to the upstream simple name the probe
    emits. ``MissingOperandException`` carries over verbatim."""
    name = type(exc).__name__
    if name == "OSError":
        return "IOException"
    return name


def _parse_java(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        case_id, _, outcome = line.partition("\t")
        result[case_id] = outcome
    return result


@requires_oracle
def test_path_construction_fuzz_parity() -> None:
    java = _parse_java(run_probe_text("PathConstructionFuzzProbe"))
    py = _pypdfbox_outcomes()
    assert set(py) == set(java), (
        f"case-id mismatch: py-only={set(py) - set(java)} "
        f"java-only={set(java) - set(py)}"
    )
    diffs = {cid: (java[cid], py[cid]) for cid in java if java[cid] != py[cid]}
    assert not diffs, (
        "path-construction operand-fuzz divergences (java, py):\n"
        + "\n".join(
            f"  {cid}: java={j!r} py={p!r}"
            for cid, (j, p) in sorted(diffs.items())
        )
    )


@pytest.mark.parametrize("case_id", _IDS)
def test_pypdfbox_outcomes_present(case_id: str) -> None:
    """Cheap non-oracle guard: every case yields a non-empty outcome so a
    builder regression can't silently drop cases when the oracle is absent."""
    out = _pypdfbox_outcomes()
    assert out[case_id]


def test_no_current_point_fallbacks() -> None:
    """Regression pin for the wave-1536 current-point fixes: ``l`` / ``c`` /
    ``v`` / ``y`` without an initial MoveTo fall back to ``move_to`` (not
    ``line_to`` / ``curve_to`` / a silent skip), and ``h`` is a no-op."""
    out = _pypdfbox_outcomes()
    assert out["l_two_nocp"].startswith("move")
    assert out["l_two_cp"].startswith("line")
    assert out["c_six_nocp"].startswith("move")
    assert out["c_six_cp"].startswith("curve")
    assert out["v_four_nocp"].startswith("move")
    assert out["v_four_cp"].startswith("curve")
    assert out["y_four_nocp"].startswith("move")
    assert out["y_four_cp"].startswith("curve")
    assert out["h_nocp"] == "|cp=none"
    assert out["h_cp"].startswith("close")


def test_whole_list_type_guard() -> None:
    """Regression pin for the wave-1536 ``c`` / ``v`` / ``y`` / ``re``
    whole-list guard: a trailing non-number operand makes the operator a
    silent no-op, mirroring upstream ``checkArrayTypesClass(operands, ...)``.
    ``m`` keeps its per-operand check (trailing non-number ignored)."""
    out = _pypdfbox_outcomes()
    assert out["c_seven_trailing_name"] == "|cp=10.000,20.000"
    assert out["v_five_trailing_null"] == "|cp=10.000,20.000"
    assert out["y_five_trailing_name"] == "|cp=10.000,20.000"
    assert out["re_five_trailing_name"] == "|cp=none"
    # m / l cast operands 0/1 individually — trailing non-number is ignored.
    assert out["m_three_trailing_name"].startswith("move")
    assert out["l_three_trailing_name_nocp"].startswith("move")

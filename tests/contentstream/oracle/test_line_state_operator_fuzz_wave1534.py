"""Differential line-state OPERATOR operand fuzz vs Apache PDFBox 3.0.7
(wave 1534).

Surface: the *operand handling* of the line-state setter operator processors
when fed malformed operand windows — too few / too many operands, wrong COS
types (name / string / null where a number/name is expected), out-of-range
cap / join style ints, negative / huge widths and miter limits, and the dash
operator's ``[array] phase`` two-operand shape with malformed arrays.

Operators covered: ``w`` (line width), ``J`` (line cap), ``j`` (line join),
``M`` (miter limit), ``d`` (dash), ``ri`` (rendering intent), ``i`` (flatness).

How the oracle works
--------------------
``oracle/probes/LineStateOperatorFuzzProbe.java`` instantiates each operator
processor and calls its ``process(Operator, List)`` DIRECTLY with a hand-built
operand list. It must call ``process`` directly rather than route through the
engine because ``PDFStreamEngine.processOperator`` swallows
``MissingOperandException`` (and friends) into ``operatorException`` — so the
arity/type contract is invisible at the engine layer. For every case it emits::

    <id>\\tERR:<SimpleExceptionName>          # process() threw
    <id>\\tOK|<line-state fingerprint>        # process() returned (maybe no-op)

The fingerprint is the post-call snapshot of every line-state field the
operators can touch (line width / cap / join / miter / flatness / dash /
rendering intent), seeded with sentinel values so a *silent ignore* (bad-type
operand → no mutation) is distinguishable from an *applied* update.

The pypdfbox side replays the IDENTICAL operand lists through the SAME canonical
operator processors (the ones ``PDFGraphicsStreamEngine`` registers) bound to a
recording engine whose ``get_graphics_state()`` returns a real
``PDGraphicsState`` and whose ``set_line_dash_pattern`` hook mirrors upstream by
storing a ``PDLineDashPattern``. Any divergence is purely operand handling.

Real bugs this wave caught
--------------------------
* ``w`` (``set_line_width.SetLineWidth``): guarded only ``operands[0]`` for
  COSNumber-ness while upstream's ``SetLineWidth`` runs
  ``checkArrayTypesClass(operands, COSNumber)`` over the WHOLE list — so a
  malformed ``5 /Name w`` half-applied in pypdfbox but is a silent no-op
  upstream. Fixed + arity (empty → ``MissingOperandException``).
* ``J`` / ``j`` / ``M`` / ``i`` were registry log-stubs — they neither threw on
  empty operands nor applied the value nor ran the whole-list guard. Ported to
  full upstream behaviour.
* ``d`` (``set_dash_pattern.SetDashPattern``): the dash-array sanitiser emptied
  the array on ANY non-number element, but upstream **breaks on the first
  non-zero numeric entry** and only empties when a non-number is reached first.
  So ``[3 /Name]`` keeps its two entries upstream (loop breaks at ``3``) but was
  wrongly solidified by pypdfbox. Fixed to the early-break semantic.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.state.set_dash_pattern import SetDashPattern
from pypdfbox.contentstream.operator.state.set_flatness import SetFlatness
from pypdfbox.contentstream.operator.state.set_line_cap_style import (
    SetLineCapStyle,
)
from pypdfbox.contentstream.operator.state.set_line_join_style import (
    SetLineJoinStyle,
)
from pypdfbox.contentstream.operator.state.set_line_miter_limit import (
    SetLineMiterLimit,
)
from pypdfbox.contentstream.operator.state.set_line_width import SetLineWidth
from pypdfbox.contentstream.operator.state.set_rendering_intent import (
    SetRenderingIntent,
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
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from tests.oracle.harness import requires_oracle, run_probe_text

# Sentinel line-state values — must match the Java probe's SENT_* constants.
_SENT_W = 777.0
_SENT_CAP = 5
_SENT_JOIN = 6
_SENT_MITER = 444.0
_SENT_FLAT = 333.0

# RenderingIntent enum NAME (not value) so the fingerprint matches Java's
# ``RenderingIntent.toString()`` which prints the enum constant name.
_RI_JAVA_NAME = {
    "AbsoluteColorimetric": "ABSOLUTE_COLORIMETRIC",
    "RelativeColorimetric": "RELATIVE_COLORIMETRIC",
    "Saturation": "SATURATION",
    "Perceptual": "PERCEPTUAL",
}


class _RecordingEngine:
    """Minimal stand-in for ``PDFGraphicsStreamEngine``: holds a real
    ``PDGraphicsState`` (seeded with sentinels) and the one engine hook the
    canonical ``d`` processor notifies (``set_line_dash_pattern``)."""

    def __init__(self) -> None:
        self.reset_state()

    def reset_state(self) -> None:
        gs = PDGraphicsState()
        gs.set_line_width(_SENT_W)
        gs.set_line_cap(_SENT_CAP)
        gs.set_line_join(_SENT_JOIN)
        gs.set_miter_limit(_SENT_MITER)
        gs.set_flatness(_SENT_FLAT)
        gs.set_line_dash_pattern(None)
        gs.set_rendering_intent(None)
        self._gs = gs

    def get_graphics_state(self) -> PDGraphicsState:
        return self._gs

    # Canonical ``SetDashPattern`` notifies via this engine hook; mirror
    # upstream by wrapping the (array, phase) into a PDLineDashPattern and
    # storing it on the graphics state, exactly as upstream's
    # ``SetLineDashPattern`` does through getGraphicsState().
    def set_line_dash_pattern(self, array: COSArray, phase: int) -> None:
        self._gs.set_line_dash_pattern(PDLineDashPattern(array, phase))

    def fingerprint(self) -> str:
        gs = self._gs
        dash = gs.get_line_dash_pattern()
        if dash is None:
            dash_str = "null"
        else:
            arr = dash.get_dash_array()
            dash_str = f"len={len(arr)},ph={dash.get_phase()}"
        ri = gs.get_rendering_intent()
        ri_str = "null" if ri is None else _RI_JAVA_NAME[ri.string_value()]
        return (
            f"w={gs.get_line_width():.2f}"
            f"|cap={gs.get_line_cap()}"
            f"|join={gs.get_line_join()}"
            f"|miter={gs.get_miter_limit():.2f}"
            f"|flat={gs.get_flatness():.2f}"
            f"|dash={dash_str}"
            f"|ri={ri_str}"
        )


# --- reusable operands (mirror the Java probe one-for-one) -----------------
_NUM = COSFloat(3.5)
_NUM2 = COSFloat(-7.0)
_INT = COSInteger.get(2)
_NEGINT = COSInteger.get(-1)
_BIGINT = COSInteger.get(99)
_NAME = COSName.get_pdf_name("Perceptual")
_BADNAME = COSName.get_pdf_name("Bogus")
_STR = COSString("x")
_NULL = COSNull.NULL


def _ops(*items: COSBase) -> list[COSBase]:
    return list(items)


def _dash_array(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(v))
    return arr


def _dash_array_with(extra: COSBase) -> COSArray:
    arr = COSArray()
    arr.add(COSFloat(3.0))
    arr.add(extra)
    return arr


# Each entry: (id, processor-class, operands).
def _cases() -> list[tuple[str, type, list[COSBase]]]:
    return [
        # w -- SetLineWidth (empty->throw, whole-list COSNumber)
        ("w_empty", SetLineWidth, _ops()),
        ("w_num", SetLineWidth, _ops(_NUM)),
        ("w_int", SetLineWidth, _ops(_INT)),
        ("w_neg", SetLineWidth, _ops(_NUM2)),
        ("w_name", SetLineWidth, _ops(_NAME)),
        ("w_str", SetLineWidth, _ops(_STR)),
        ("w_null", SetLineWidth, _ops(_NULL)),
        ("w_num_extra_num", SetLineWidth, _ops(_NUM, _NUM2)),
        ("w_num_extra_name", SetLineWidth, _ops(_NUM, _NAME)),
        # J -- SetLineCapStyle (empty->throw, whole-list, no clamp)
        ("j_cap_empty", SetLineCapStyle, _ops()),
        ("j_cap_zero", SetLineCapStyle, _ops(COSInteger.get(0))),
        ("j_cap_two", SetLineCapStyle, _ops(_INT)),
        ("j_cap_neg", SetLineCapStyle, _ops(_NEGINT)),
        ("j_cap_big", SetLineCapStyle, _ops(_BIGINT)),
        ("j_cap_float", SetLineCapStyle, _ops(_NUM)),
        ("j_cap_name", SetLineCapStyle, _ops(_NAME)),
        ("j_cap_str", SetLineCapStyle, _ops(_STR)),
        ("j_cap_extra_name", SetLineCapStyle, _ops(_INT, _NAME)),
        # j -- SetLineJoinStyle
        ("j_join_empty", SetLineJoinStyle, _ops()),
        ("j_join_zero", SetLineJoinStyle, _ops(COSInteger.get(0))),
        ("j_join_two", SetLineJoinStyle, _ops(_INT)),
        ("j_join_neg", SetLineJoinStyle, _ops(_NEGINT)),
        ("j_join_big", SetLineJoinStyle, _ops(_BIGINT)),
        ("j_join_name", SetLineJoinStyle, _ops(_NAME)),
        ("j_join_extra_name", SetLineJoinStyle, _ops(_INT, _NAME)),
        # M -- SetLineMiterLimit (empty->throw, whole-list, no clamp)
        ("m_empty", SetLineMiterLimit, _ops()),
        ("m_num", SetLineMiterLimit, _ops(_NUM)),
        ("m_neg", SetLineMiterLimit, _ops(_NUM2)),
        ("m_zero", SetLineMiterLimit, _ops(COSFloat(0.0))),
        ("m_name", SetLineMiterLimit, _ops(_NAME)),
        ("m_str", SetLineMiterLimit, _ops(_STR)),
        ("m_num_extra_name", SetLineMiterLimit, _ops(_NUM, _NAME)),
        # i -- SetFlatness
        ("i_empty", SetFlatness, _ops()),
        ("i_num", SetFlatness, _ops(_NUM)),
        ("i_neg", SetFlatness, _ops(_NUM2)),
        ("i_name", SetFlatness, _ops(_NAME)),
        ("i_null", SetFlatness, _ops(_NULL)),
        ("i_num_extra_name", SetFlatness, _ops(_NUM, _NAME)),
        # ri -- SetRenderingIntent (empty->throw, get(0) instanceof COSName)
        ("ri_empty", SetRenderingIntent, _ops()),
        ("ri_known", SetRenderingIntent, _ops(_NAME)),
        ("ri_unknown", SetRenderingIntent, _ops(_BADNAME)),
        ("ri_num", SetRenderingIntent, _ops(_NUM)),
        ("ri_str", SetRenderingIntent, _ops(_STR)),
        ("ri_null", SetRenderingIntent, _ops(_NULL)),
        ("ri_name_extra", SetRenderingIntent, _ops(_NAME, _NUM)),
        # d -- SetDashPattern (<2->throw, array+number, sanitize early-break)
        ("d_empty", SetDashPattern, _ops()),
        ("d_one", SetDashPattern, _ops(_dash_array(3.0, 2.0))),
        ("d_solid", SetDashPattern, _ops(COSArray(), COSInteger.get(0))),
        (
            "d_arr_phase",
            SetDashPattern,
            _ops(_dash_array(3.0, 2.0), COSInteger.get(1)),
        ),
        (
            "d_all_zero",
            SetDashPattern,
            _ops(_dash_array(0.0, 0.0), COSInteger.get(0)),
        ),
        (
            "d_nonnum_entry",
            SetDashPattern,
            _ops(_dash_array_with(_NAME), COSInteger.get(0)),
        ),
        ("d_first_not_array", SetDashPattern, _ops(_NUM, COSInteger.get(0))),
        ("d_phase_not_num", SetDashPattern, _ops(_dash_array(3.0, 2.0), _NAME)),
        (
            "d_phase_float",
            SetDashPattern,
            _ops(_dash_array(3.0, 2.0), COSFloat(2.9)),
        ),
        (
            "d_extra",
            SetDashPattern,
            _ops(_dash_array(3.0, 2.0), COSInteger.get(1), _NUM),
        ),
    ]


_CASES = _cases()
_IDS = [c[0] for c in _CASES]


def _pypdfbox_outcomes() -> dict[str, str]:
    """Drive every case through the recording engine, returning id -> outcome
    matching the Java probe's projection."""
    engine = _RecordingEngine()
    out: dict[str, str] = {}
    for case_id, proc_cls, operands in _CASES:
        engine.reset_state()
        proc = proc_cls()
        proc.set_context(engine)
        op = Operator.get_operator(proc.get_name())
        try:
            proc.process(op, operands)
        except OSError as exc:
            out[case_id] = f"ERR:{type(exc).__name__}"
            continue
        out[case_id] = "OK|" + engine.fingerprint()
    return out


def _parse_java(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        case_id, _, outcome = line.partition("\t")
        result[case_id] = outcome
    return result


@requires_oracle
def test_line_state_operator_fuzz_parity() -> None:
    java = _parse_java(run_probe_text("LineStateOperatorFuzzProbe"))
    py = _pypdfbox_outcomes()
    assert set(py) == set(java), (
        f"case-id mismatch: py-only={set(py) - set(java)} "
        f"java-only={set(java) - set(py)}"
    )
    diffs = {
        cid: (java[cid], py[cid]) for cid in java if java[cid] != py[cid]
    }
    assert not diffs, (
        "line-operator operand-fuzz divergences (java, py):\n"
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


def test_whole_list_type_guard() -> None:
    """Regression pin: a trailing non-number operand on the numeric line-state
    operators (w / J / j / M / i) makes them a silent no-op (whole-list guard),
    matching upstream's ``checkArrayTypesClass(operands, COSNumber.class)``."""
    out = _pypdfbox_outcomes()
    assert f"w={_SENT_W:.2f}" in out["w_num_extra_name"]
    assert f"cap={_SENT_CAP}" in out["j_cap_extra_name"]
    assert f"join={_SENT_JOIN}" in out["j_join_extra_name"]
    assert f"miter={_SENT_MITER:.2f}" in out["m_num_extra_name"]
    assert f"flat={_SENT_FLAT:.2f}" in out["i_num_extra_name"]
    # ...but a trailing extra NUMBER still applies (first operand used).
    assert "w=3.50" in out["w_num_extra_num"]


def test_empty_operand_raises() -> None:
    """Each line-state operator throws MissingOperandException on empty
    operands (d throws on <2)."""
    out = _pypdfbox_outcomes()
    for cid in (
        "w_empty",
        "j_cap_empty",
        "j_join_empty",
        "m_empty",
        "i_empty",
        "ri_empty",
        "d_empty",
        "d_one",
    ):
        assert out[cid] == "ERR:MissingOperandException", (cid, out[cid])


def test_dash_array_early_break_sanitize() -> None:
    """Pin the wave-1534 dash fix: ``[3 /Name]`` keeps both entries (loop
    breaks at the non-zero number before reaching the name), while a
    leading-zero array with a non-number is solidified to empty."""
    out = _pypdfbox_outcomes()
    assert "dash=len=2,ph=0" in out["d_nonnum_entry"]
    # All-zero numeric array is kept as-is (len=2) — never solidified.
    assert "dash=len=2,ph=0" in out["d_all_zero"]
    # Phase float truncates to int.
    assert "dash=len=2,ph=2" in out["d_phase_float"]
    # First operand not an array -> silent no-op (dash stays null).
    assert "dash=null" in out["d_first_not_array"]
    assert "dash=null" in out["d_phase_not_num"]

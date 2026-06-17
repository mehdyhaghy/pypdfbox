"""Differential text-state / text-positioning OPERATOR operand fuzz vs
Apache PDFBox 3.0.7 (wave 1525).

Surface: the *operand handling* of the text-state setter and text-positioning
operator processors when fed malformed operand windows — too few / too many
operands, wrong COS types (name / string / array / null where a number is
expected), out-of-range render modes, and the whole-list-vs-prefix type guard
of ``Tm``. Companion to the wave's matrix/show-text decomposition probes
(``TextStateMatrixProbe`` / ``ShowTextLineDecompProbe``) which exercise the
*math*; this one pins the *gatekeeping*.

How the oracle works
--------------------
``oracle/probes/TextStateOperatorFuzzProbe.java`` instantiates each operator
processor and calls its ``process(Operator, List)`` DIRECTLY with a hand-built
operand list. It must call ``process`` directly rather than route through the
engine because ``PDFStreamEngine.processOperator`` swallows
``MissingOperandException`` (and friends) into ``operatorException`` — so the
arity/type contract is invisible at the engine layer. For every case it emits::

    <id>\\tERR:<SimpleExceptionName>          # process() threw
    <id>\\tOK|<text-state fingerprint>        # process() returned (maybe no-op)

The fingerprint is the post-call snapshot of every text-state field the
operators can touch (Tc/Tw/TL/Tz/Ts/Tr/Tf + the text matrix) so a *silent
ignore* (bad-type operand → no mutation) is distinguishable from an *applied*
update. State is reset to PDF defaults + a sentinel text matrix before each case.

The pypdfbox side replays the IDENTICAL operand lists through the SAME canonical
operator processors (the substantive ones ``PDFGraphicsStreamEngine`` registers
— ``set_char_spacing.SetCharSpacing`` etc., not the lite registry stubs) bound
to a *recording* engine that mirrors upstream's ``PDGraphicsState`` text-state
mutation, and emits the same fingerprint string. Any divergence is purely
operand-handling behaviour.

Real bug this wave caught
-------------------------
``Tm`` (``set_matrix.SetMatrix``): pypdfbox guarded only ``operands[:6]`` for
COSNumber-ness, while upstream's ``SetMatrix`` calls
``checkArrayTypesClass(operands, COSNumber.class)`` over the WHOLE list. So a
malformed ``a b c d e f /Name Tm`` (seven operands, trailing non-number) made
pypdfbox apply the matrix while upstream silently dropped it. Fixed to guard the
full operand list; the ``tm_seven_trailing_*`` cases pin it.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.text.move_text import MoveText
from pypdfbox.contentstream.operator.text.move_text_set_leading import (
    MoveTextSetLeading,
)
from pypdfbox.contentstream.operator.text.next_line_op import NextLine
from pypdfbox.contentstream.operator.text.set_char_spacing import SetCharSpacing
from pypdfbox.contentstream.operator.text.set_font_and_size import SetFontAndSize
from pypdfbox.contentstream.operator.text.set_horizontal_text_scaling import (
    SetHorizontalTextScaling,
)
from pypdfbox.contentstream.operator.text.set_matrix import SetMatrix
from pypdfbox.contentstream.operator.text.set_text_leading_op import SetTextLeading
from pypdfbox.contentstream.operator.text.set_text_rendering_mode_op import (
    SetTextRenderingMode,
)
from pypdfbox.contentstream.operator.text.set_text_rise_op import SetTextRise
from pypdfbox.contentstream.operator.text.set_word_spacing_op import SetWordSpacing
from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.graphics.state.pd_text_state import PDTextState
from pypdfbox.pdmodel.graphics.state.rendering_mode import RenderingMode
from tests.oracle.harness import requires_oracle, run_probe_text

# Sentinel text-matrix translate so a silent-ignore (no mutation) reads
# differently from an applied update — must match the Java probe's SENTINEL.
_SENT_E = 999.0
_SENT_F = 888.0
_SENT_A = 1.0


class _RecordingTextState:
    """Mirror of upstream ``PDGraphicsState`` for the fingerprint: just a
    ``PDTextState`` reachable via ``get_text_state`` (which ``Tz`` writes to
    directly)."""

    def __init__(self) -> None:
        self._text_state = PDTextState()

    def get_text_state(self) -> PDTextState:
        return self._text_state


class _RecordingEngine(PDFStreamEngine):
    """A ``PDFStreamEngine`` whose text-state notification hooks actually
    mutate a ``PDTextState`` + text matrices, so the post-call fingerprint
    matches Apache PDFBox's ``PDGraphicsState``-backed engine.

    The base engine's hooks are cluster-#2 no-ops by design (text-state
    tracking lives in the rendering cluster); this subclass supplies the
    minimal tracking the differential needs without touching production."""

    def __init__(self) -> None:
        super().__init__()
        self._gs = _RecordingTextState()
        self.reset_state()

    # -- per-case reset -----------------------------------------------------
    def reset_state(self) -> None:
        self._gs = _RecordingTextState()
        # 6-float affine [a b c d e f]; sentinel translate so a no-op shows.
        self._tm = [_SENT_A, 0.0, 0.0, 1.0, _SENT_E, _SENT_F]
        self._tlm = [_SENT_A, 0.0, 0.0, 1.0, _SENT_E, _SENT_F]
        self._font_set = False

    # -- graphics-state access (Tz writes through this) ---------------------
    def get_graphics_state(self) -> _RecordingTextState:
        return self._gs

    # -- text-state notification hooks (Tc/Tw/TL/Ts/Tr/Tf) ------------------
    def set_character_spacing(self, spacing: float) -> None:
        self._gs.get_text_state().set_character_spacing(spacing)

    def set_word_spacing(self, spacing: float) -> None:
        self._gs.get_text_state().set_word_spacing(spacing)

    def set_text_leading(self, leading: float) -> None:
        self._gs.get_text_state().set_leading(leading)

    def get_text_leading(self) -> float:
        return self._gs.get_text_state().get_leading()

    def set_text_rise(self, rise: float) -> None:
        self._gs.get_text_state().set_rise(rise)

    def set_text_rendering_mode(self, mode: int) -> None:
        self._gs.get_text_state().set_rendering_mode(RenderingMode.from_int(mode))

    def set_horizontal_scaling(self, scaling: float) -> None:
        self._gs.get_text_state().set_horizontal_scaling(scaling)

    def set_font(self, font_name: COSName, font_size: float) -> None:
        # Mirror upstream: font size is set even when the name misses in
        # resources; the font object itself stays unset (None / null).
        self._gs.get_text_state().set_font_size(font_size)

    # -- text-matrix hooks (Tm writes both; Td concatenates) ----------------
    def set_text_matrix(self, matrix: list[float] | None) -> None:
        if matrix is not None:
            self._tm = list(matrix)

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        if matrix is not None:
            self._tlm = list(matrix)

    def get_text_line_matrix(self) -> list[float]:
        # Overridden (non-None) so MoveText's upstream null-guard is active,
        # matching the Java probe which seeds a real text-line matrix.
        return self._tlm

    def move_text_position(self, tx: float, ty: float) -> None:
        # Upstream MoveText: textLineMatrix.concatenate(translation(tx,ty))
        # where concatenate(m) sets this = m * this; then textMatrix = clone.
        self._tlm = _mul(_translation(tx, ty), self._tlm)
        self._tm = list(self._tlm)

    # -- fingerprint --------------------------------------------------------
    def fingerprint(self) -> str:
        ts = self._gs.get_text_state()
        font = "null"  # base engine never resolves a real font object
        return (
            f"tc={ts.get_character_spacing():.2f}"
            f"|tw={ts.get_word_spacing():.2f}"
            f"|tl={ts.get_leading():.2f}"
            f"|tz={ts.get_horizontal_scaling():.2f}"
            f"|ts={ts.get_rise():.2f}"
            f"|tr={ts.get_rendering_mode().int_value()}"
            f"|fs={ts.get_font_size():.2f}"
            f"|font={font}"
            f"|tmx={self._tm[4]:.2f}"
            f"|tmy={self._tm[5]:.2f}"
            f"|tma={self._tm[0]:.2f}"
        )


def _translation(tx: float, ty: float) -> list[float]:
    return [1.0, 0.0, 0.0, 1.0, tx, ty]


def _mul(m1: list[float], m2: list[float]) -> list[float]:
    """Row-vector affine product matching upstream ``Matrix.multiplyArrays``
    (result = m1 * m2)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return [
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    ]


# --- reusable operands (mirror the Java probe one-for-one) -----------------
_NUM = COSFloat(3.5)
_NUM2 = COSFloat(-7.0)
_INT = COSInteger.get(2)
_NAME = COSName.get_pdf_name("F1")
_STR = COSString("x")
_ARR = COSArray()
_NULL = COSNull.NULL


def _ops(*items: COSBase) -> list[COSBase]:
    return list(items)


# Each entry: (id, processor-factory, operands). The processor is rebuilt per
# case so its context binds to the shared recording engine.
def _cases() -> list[tuple[str, type, list[COSBase]]]:
    return [
        # Tc -- empty->throw, last-arg, instanceof
        ("tc_empty", SetCharSpacing, _ops()),
        ("tc_num", SetCharSpacing, _ops(_NUM)),
        ("tc_name", SetCharSpacing, _ops(_NAME)),
        ("tc_str", SetCharSpacing, _ops(_STR)),
        ("tc_null", SetCharSpacing, _ops(_NULL)),
        ("tc_extra_last_num", SetCharSpacing, _ops(_NAME, _NUM)),
        ("tc_extra_last_name", SetCharSpacing, _ops(_NUM, _NAME)),
        # Tw -- empty->SILENT, get(0), instanceof
        ("tw_empty", SetWordSpacing, _ops()),
        ("tw_num", SetWordSpacing, _ops(_NUM)),
        ("tw_name", SetWordSpacing, _ops(_NAME)),
        ("tw_str", SetWordSpacing, _ops(_STR)),
        ("tw_extra", SetWordSpacing, _ops(_NUM, _NUM2)),
        # TL -- empty->throw, get(0), instanceof
        ("tl_empty", SetTextLeading, _ops()),
        ("tl_num", SetTextLeading, _ops(_NUM)),
        ("tl_name", SetTextLeading, _ops(_NAME)),
        ("tl_arr", SetTextLeading, _ops(_ARR)),
        # Tz -- empty->throw, get(0), instanceof
        ("tz_empty", SetHorizontalTextScaling, _ops()),
        ("tz_num", SetHorizontalTextScaling, _ops(_NUM)),
        ("tz_zero", SetHorizontalTextScaling, _ops(COSFloat(0.0))),
        ("tz_neg", SetHorizontalTextScaling, _ops(COSFloat(-50.0))),
        ("tz_name", SetHorizontalTextScaling, _ops(_NAME)),
        ("tz_null", SetHorizontalTextScaling, _ops(_NULL)),
        # Ts -- empty->SILENT, get(0), instanceof
        ("ts_empty", SetTextRise, _ops()),
        ("ts_num", SetTextRise, _ops(_NUM)),
        ("ts_name", SetTextRise, _ops(_NAME)),
        ("ts_str", SetTextRise, _ops(_STR)),
        # Tr -- empty->throw, get(0), instanceof, range-check
        ("tr_empty", SetTextRenderingMode, _ops()),
        ("tr_zero", SetTextRenderingMode, _ops(COSInteger.get(0))),
        ("tr_seven", SetTextRenderingMode, _ops(COSInteger.get(7))),
        ("tr_eight", SetTextRenderingMode, _ops(COSInteger.get(8))),
        ("tr_neg", SetTextRenderingMode, _ops(COSInteger.get(-1))),
        ("tr_float_in_range", SetTextRenderingMode, _ops(COSFloat(2.9))),
        ("tr_name", SetTextRenderingMode, _ops(_NAME)),
        ("tr_str", SetTextRenderingMode, _ops(_STR)),
        # Tf -- <2->throw, name+number
        ("tf_empty", SetFontAndSize, _ops()),
        ("tf_one", SetFontAndSize, _ops(_NAME)),
        ("tf_unknown_font", SetFontAndSize, _ops(_NAME, _NUM)),
        ("tf_num_for_name", SetFontAndSize, _ops(_NUM, _NUM)),
        ("tf_str_for_name", SetFontAndSize, _ops(_STR, _NUM)),
        ("tf_name_for_size", SetFontAndSize, _ops(_NAME, _NAME)),
        ("tf_null_size", SetFontAndSize, _ops(_NAME, _NULL)),
        ("tf_extra", SetFontAndSize, _ops(_NAME, _NUM, _NUM2)),
        # Td -- <2->throw, get(0)/get(1) instanceof
        ("td_empty", MoveText, _ops()),
        ("td_one", MoveText, _ops(_NUM)),
        ("td_two", MoveText, _ops(_NUM, _NUM2)),
        ("td_name_first", MoveText, _ops(_NAME, _NUM2)),
        ("td_name_second", MoveText, _ops(_NUM, _NAME)),
        ("td_both_name", MoveText, _ops(_NAME, _NAME)),
        ("td_extra", MoveText, _ops(_NUM, _NUM2, _NUM)),
        # TD -- <2->throw, get(1) instanceof
        ("td2_empty", MoveTextSetLeading, _ops()),
        ("td2_one", MoveTextSetLeading, _ops(_NUM)),
        ("td2_two", MoveTextSetLeading, _ops(_NUM, _NUM2)),
        ("td2_name_second", MoveTextSetLeading, _ops(_NUM, _NAME)),
        ("td2_name_first", MoveTextSetLeading, _ops(_NAME, _NUM2)),
        # Tm -- <6->throw, checkArrayTypesClass over the WHOLE list
        ("tm_empty", SetMatrix, _ops()),
        ("tm_five", SetMatrix, _ops(_NUM, _NUM, _NUM, _NUM, _NUM)),
        ("tm_six", SetMatrix, _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NUM)),
        ("tm_six_with_int", SetMatrix, _ops(_INT, _NUM, _NUM, _NUM, _NUM, _NUM)),
        ("tm_six_one_name", SetMatrix, _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NAME)),
        (
            "tm_six_first_name",
            SetMatrix,
            _ops(_NAME, _NUM, _NUM, _NUM, _NUM, _NUM),
        ),
        (
            "tm_seven_all_num",
            SetMatrix,
            _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NUM, _NUM),
        ),
        (
            "tm_seven_trailing_name",
            SetMatrix,
            _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NUM, _NAME),
        ),
        (
            "tm_seven_trailing_null",
            SetMatrix,
            _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NUM, _NULL),
        ),
        # T* -- no operand check at all
        ("tstar_empty", NextLine, _ops()),
        ("tstar_extra", NextLine, _ops(_NUM, _NUM2)),
    ]


_CASES = _cases()
_IDS = [c[0] for c in _CASES]


def _register_text_operators(engine: _RecordingEngine) -> None:
    """Register the substantive text operators so the TD / T* decomposition
    path fires through ``process_operator`` (the realistic engine config) —
    mirroring the Java probe's ``addOperator`` calls."""
    for proc_cls in (
        SetCharSpacing,
        SetWordSpacing,
        SetTextLeading,
        SetHorizontalTextScaling,
        SetTextRise,
        SetTextRenderingMode,
        SetFontAndSize,
        MoveText,
        MoveTextSetLeading,
        SetMatrix,
        NextLine,
    ):
        engine.add_operator(proc_cls())


def _pypdfbox_outcomes() -> dict[str, str]:
    """Drive every case through the recording engine, returning id -> outcome
    matching the Java probe's projection."""
    engine = _RecordingEngine()
    _register_text_operators(engine)
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


# Map pypdfbox's MissingOperandException simple-name (matches upstream's
# MissingOperandException). Both extend the IOException/OSError analogue.
_ERR_RENAME = {"ERR:MissingOperandException": "ERR:MissingOperandException"}


@requires_oracle
def test_text_state_operator_fuzz_parity() -> None:
    java = _parse_java(run_probe_text("TextStateOperatorFuzzProbe"))
    py = _pypdfbox_outcomes()
    assert set(py) == set(java), (
        f"case-id mismatch: py-only={set(py) - set(java)} "
        f"java-only={set(java) - set(py)}"
    )
    diffs = {
        cid: (java[cid], py[cid])
        for cid in java
        if _ERR_RENAME.get(java[cid], java[cid]) != py[cid]
    }
    assert not diffs, "text-operator operand-fuzz divergences (java, py):\n" + "\n".join(
        f"  {cid}: java={j!r} py={p!r}" for cid, (j, p) in sorted(diffs.items())
    )


@pytest.mark.parametrize("case_id", _IDS)
def test_pypdfbox_outcomes_present(case_id: str) -> None:
    """Cheap non-oracle guard: every case yields a non-empty outcome so a
    builder regression can't silently drop cases when the oracle is absent."""
    out = _pypdfbox_outcomes()
    assert out[case_id]


def test_tm_whole_list_type_guard() -> None:
    """Regression pin for the wave-1525 ``Tm`` fix: a seventh trailing
    non-number operand makes ``Tm`` a silent no-op (whole-list guard),
    matching upstream's ``checkArrayTypesClass(operands, COSNumber.class)``."""
    out = _pypdfbox_outcomes()
    # All-number 7-operand Tm applies (uses first six).
    assert "tmx=3.50" in out["tm_seven_all_num"]
    # Trailing non-number 7-operand Tm does NOT mutate the matrix.
    assert f"tmx={_SENT_E:.2f}" in out["tm_seven_trailing_name"]
    assert f"tmx={_SENT_E:.2f}" in out["tm_seven_trailing_null"]
    # Six-operand with one non-number is likewise a silent no-op.
    assert f"tmx={_SENT_E:.2f}" in out["tm_six_one_name"]

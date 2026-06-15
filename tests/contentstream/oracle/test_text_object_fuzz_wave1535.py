"""Differential ``BT`` / ``ET`` text-object operator fuzz vs Apache PDFBox
3.0.7 (wave 1535).

Surface: the begin/end text-object operator processors
(``pypdfbox.contentstream.operator.text.begin_text.BeginText`` /
``end_text.EndText``, mirroring
``org.apache.pdfbox.contentstream.operator.text.BeginText`` / ``EndText``) and
the text-matrix reset they perform.

Upstream contract
-----------------
* ``BeginText.process`` resets BOTH the text matrix and the text-line matrix to
  the identity matrix (``context.setTextMatrix(new Matrix())`` /
  ``setTextLineMatrix(new Matrix())``) then calls ``context.beginText()``.
* ``EndText.process`` clears BOTH matrices to ``null``
  (``context.setTextLineMatrix(null)`` / ``setTextMatrix(null)``) then calls
  ``context.endText()``.
* Neither validates its operand window — extra operands are silently ignored
  and neither operator ever throws, so an ``ET`` with no preceding ``BT``
  (underflow), a doubled ``ET``, and a re-opened (nested) ``BT`` are all
  tolerated.

How the oracle works
--------------------
``oracle/probes/TextObjectFuzzProbe.java`` instantiates a ``BeginText`` /
``EndText`` bound to a recording ``PDFStreamEngine`` subclass that actually
stores the matrices the operators write (the stock base engine's text-state
tracking lives in the rendering cluster, so a bare engine would discard them).
It calls ``process(Operator, List)`` DIRECTLY — not via
``processOperator`` which would swallow any exception into
``operatorException`` — for a fixed sequence of fuzz cases, and after every call
snapshots ``getTextMatrix()`` / ``getTextLineMatrix()`` plus the begin/end call
counts. Each step emits ``<id>\\tOK|<fingerprint>`` or ``<id>\\tERR:<Exc>``.

The pypdfbox side replays the IDENTICAL steps through the production
``BeginText`` / ``EndText`` bound to a recording engine that mirrors upstream's
matrix storage (the base engine's notification hooks are cluster-#2 no-ops by
design — text-matrix state is held in the rendering cluster), and emits the
same fingerprint. Any divergence is purely BT/ET operand/reset behaviour.

No divergence was found this wave: pypdfbox's BT identity-reset, ET null-clear,
operand tolerance, and underflow/nesting handling all match Apache PDFBox.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.text.begin_text import BeginText
from pypdfbox.contentstream.operator.text.end_text import EndText
from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import COSArray, COSBase, COSFloat, COSName, COSNull, COSString
from tests.oracle.harness import requires_oracle, run_probe_text

_IDENTITY = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


class _RecordingEngine(PDFStreamEngine):
    """A ``PDFStreamEngine`` whose text-matrix notification hooks actually
    store the 6-float matrix (or ``None``) the BT/ET operators write, plus
    begin/end call counters — mirroring the Java probe's recording engine.

    The base engine's ``set_text_matrix`` / ``set_text_line_matrix`` hooks are
    cluster-#2 no-ops by design (text-matrix state lives in the rendering
    cluster); this subclass supplies the minimal tracking the differential
    needs without touching production code."""

    def __init__(self) -> None:
        super().__init__()
        self.reset_state()

    def reset_state(self) -> None:
        # Sentinel translate so a no-op reads differently from a real reset.
        self._tm: list[float] | None = [1.0, 0.0, 0.0, 1.0, 999.0, 888.0]
        self._tlm: list[float] | None = [1.0, 0.0, 0.0, 1.0, 777.0, 666.0]
        self._begin_count = 0
        self._end_count = 0

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        self._tm = None if matrix is None else list(matrix)

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        self._tlm = None if matrix is None else list(matrix)

    def get_text_matrix(self) -> Any:
        return self._tm

    def get_text_line_matrix(self) -> Any:
        return self._tlm

    def begin_text(self) -> None:
        self._begin_count += 1

    def end_text(self) -> None:
        self._end_count += 1

    @staticmethod
    def _mat(m: list[float] | None) -> str:
        if m is None:
            return "null"
        return "[" + " ".join(f"{v:.2f}" for v in m) + "]"

    def fingerprint(self) -> str:
        return (
            f"tm={self._mat(self._tm)}"
            f"|tlm={self._mat(self._tlm)}"
            f"|bc={self._begin_count}"
            f"|ec={self._end_count}"
        )


_NUM = COSFloat(3.5)
_NAME = COSName.get_pdf_name("F1")
_STR = COSString("x")
_NULL = COSNull.NULL
_ARR = COSArray()


def _ops(*items: COSBase) -> list[COSBase]:
    return list(items)


def _run(
    engine: _RecordingEngine, proc: Any, operands: list[COSBase]
) -> str:
    op = Operator.get_operator(proc.get_name())
    try:
        proc.process(op, operands)
    except OSError as exc:  # MissingOperandException analogue
        return f"ERR:{type(exc).__name__}"
    return "OK|" + engine.fingerprint()


def _set_tm(engine: _RecordingEngine, m: list[float]) -> None:
    engine.set_text_matrix(m)
    engine.set_text_line_matrix(m)


def _pypdfbox_outcomes() -> dict[str, str]:
    """Replay the Java probe's exact step sequence and return id -> outcome."""
    engine = _RecordingEngine()
    bt = BeginText()
    bt.set_context(engine)
    et = EndText()
    et.set_context(engine)
    out: dict[str, str] = {}

    engine.reset_state()
    out["bt_empty"] = _run(engine, bt, _ops())

    engine.reset_state()
    out["bt_extra_num"] = _run(engine, bt, _ops(_NUM))
    engine.reset_state()
    out["bt_extra_many"] = _run(engine, bt, _ops(_NUM, _NAME, _STR, _NULL, _ARR))

    engine.reset_state()
    out["et_empty"] = _run(engine, et, _ops())

    engine.reset_state()
    out["et_extra_num"] = _run(engine, et, _ops(_NUM))
    engine.reset_state()
    out["et_extra_many"] = _run(engine, et, _ops(_NUM, _NAME, _STR))

    engine.reset_state()
    out["et_underflow"] = _run(engine, et, _ops())

    engine.reset_state()
    out["balanced_bt"] = _run(engine, bt, _ops())
    out["balanced_et"] = _run(engine, et, _ops())

    engine.reset_state()
    out["nested_bt1"] = _run(engine, bt, _ops())
    _set_tm(engine, [2.0, 0.0, 0.0, 2.0, 50.0, 60.0])
    out["nested_bt2"] = _run(engine, bt, _ops())

    engine.reset_state()
    out["double_et1"] = _run(engine, et, _ops())
    out["double_et2"] = _run(engine, et, _ops())

    engine.reset_state()
    out["seq_bt"] = _run(engine, bt, _ops())
    _set_tm(engine, [1.0, 0.0, 0.0, 1.0, 100.0, 200.0])
    out["seq_after_tm"] = "OK|" + engine.fingerprint()
    out["seq_et"] = _run(engine, et, _ops())

    return out


def _parse_java(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        case_id, _, outcome = line.partition("\t")
        result[case_id] = outcome
    return result


_IDS = list(_pypdfbox_outcomes())


@requires_oracle
def test_text_object_fuzz_parity() -> None:
    java = _parse_java(run_probe_text("TextObjectFuzzProbe"))
    py = _pypdfbox_outcomes()
    assert set(py) == set(java), (
        f"case-id mismatch: py-only={set(py) - set(java)} "
        f"java-only={set(java) - set(py)}"
    )
    diffs = {cid: (java[cid], py[cid]) for cid in java if java[cid] != py[cid]}
    assert not diffs, "BT/ET text-object fuzz divergences (java, py):\n" + "\n".join(
        f"  {cid}: java={j!r} py={p!r}" for cid, (j, p) in sorted(diffs.items())
    )


@pytest.mark.parametrize("case_id", _IDS)
def test_pypdfbox_outcomes_present(case_id: str) -> None:
    """Cheap non-oracle guard: every case yields a non-empty outcome so a
    builder regression can't silently drop cases when the oracle is absent."""
    out = _pypdfbox_outcomes()
    assert out[case_id]


def test_bt_resets_both_matrices_to_identity() -> None:
    """``BT`` resets text + text-line matrix to identity and never throws,
    ignoring any extra operands."""
    engine = _RecordingEngine()
    bt = BeginText()
    bt.set_context(engine)
    engine.reset_state()
    bt.process(Operator.get_operator(bt.get_name()), _ops(_NUM, _NAME))
    assert engine.get_text_matrix() == _IDENTITY
    assert engine.get_text_line_matrix() == _IDENTITY
    assert engine._begin_count == 1


def test_et_clears_both_matrices_even_without_bt() -> None:
    """``ET`` clears text + text-line matrix to ``None`` and tolerates being
    called with no preceding ``BT`` (underflow) and with extra operands."""
    engine = _RecordingEngine()
    et = EndText()
    et.set_context(engine)
    engine.reset_state()
    et.process(Operator.get_operator(et.get_name()), _ops(_NUM, _STR))
    assert engine.get_text_matrix() is None
    assert engine.get_text_line_matrix() is None
    assert engine._end_count == 1

"""Differential fuzz of the ``q`` (Save) / ``Q`` (Restore) graphics-state
operator processors and the engine graphics-state stack nesting, vs Apache
PDFBox 3.0.7 (wave 1535).

Surface
-------
* ``q`` — :class:`SaveGraphicsState` (upstream
  ``org.apache.pdfbox.contentstream.operator.state.Save``): unconditionally
  calls ``getContext().saveGraphicsState()`` and IGNORES its operand list
  entirely — no arity / type guard. Each ``q`` pushes a clone of the current
  top frame (depth + 1).
* ``Q`` — :class:`RestoreGraphicsState` (upstream
  ``...operator.state.Restore``): ``if getGraphicsStackSize() > 1 ->
  restoreGraphicsState() (pop, depth - 1); else raise
  EmptyGraphicsStackException``. The operator THROWS on a single-frame / empty
  stack (PDFBOX-161); the lenient log-and-skip happens one level up in
  ``operatorException``, not in the operator. Operands on ``Q`` are ignored.

How the oracle works
--------------------
``oracle/probes/SaveRestoreStateFuzzProbe.java`` drives the real upstream
``Save`` / ``Restore`` processors against a :class:`PDFStreamEngine` whose three
graphics-stack hooks are overridden with a plain depth counter seeded at 1 (the
post-``initPage`` starting depth a real page run has — the base engine's
``saveGraphicsState`` NPEs on an empty deque and ``initPage`` is private, so the
counter models the exact push/pop/size arithmetic without a real PDPage). For
each q/Q step sequence it emits::

    <id>\\t<size-after>          # ran clean; final stack depth
    <id>\\tERR:<SimpleName>@<n>  # threw; n = stack depth at the throw

The pypdfbox side replays the IDENTICAL sequences through the SAME canonical
:class:`SaveGraphicsState` / :class:`RestoreGraphicsState` processors bound to an
engine that overrides the same three hooks with a depth counter seeded at 1, and
emits the same projection.

Divergences
-----------
NONE. pypdfbox's ``Save`` / ``Restore`` operators already mirror upstream
3.0.7 byte-for-byte: ``q`` ignores operands and pushes; ``Q`` pops only when
``get_graphics_stack_size() > 1`` and otherwise raises
:class:`EmptyGraphicsStackException`. (The wave brief's claim that upstream
"logs and skips rather than throwing" describes the engine-level
``operator_exception`` swallow, not the operator itself — the decompiled 3.0.7
``Restore.process`` bytecode throws, which the live oracle confirms.) No
production change was required.
"""

from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.state.empty_graphics_stack_exception import (
    EmptyGraphicsStackException,
)
from pypdfbox.contentstream.operator.state.restore_graphics_state import (
    RestoreGraphicsState,
)
from pypdfbox.contentstream.operator.state.save_graphics_state import (
    SaveGraphicsState,
)
from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import COSBase, COSFloat, COSInteger, COSName
from tests.oracle.harness import requires_oracle, run_probe_text


class _DepthEngine(PDFStreamEngine):
    """Engine that shadows the graphics-stack hooks with a plain depth counter
    seeded at 1, mirroring the Java probe's ``ProbeEngine`` exactly."""

    def __init__(self) -> None:
        super().__init__()
        self._depth = 1

    def save_graphics_state(self) -> None:
        self._depth += 1

    def restore_graphics_state(self) -> None:
        self._depth -= 1

    def get_graphics_stack_size(self) -> int:
        return self._depth


def _no_operands() -> list[COSBase]:
    return []


def _some_operands() -> list[COSBase]:
    return [COSFloat(1.5), COSInteger.get(2), COSName.get_pdf_name("X")]


# (id, steps, q-operands, Q-operands) — mirrors the Java probe one-for-one.
def _cases() -> list[tuple[str, str, list[COSBase], list[COSBase]]]:
    none = _no_operands
    some = _some_operands
    return [
        ("q_only", "q", none(), none()),
        ("qq", "qq", none(), none()),
        ("qqq", "qqq", none(), none()),
        ("q_then_Q", "qQ", none(), none()),
        ("qq_QQ", "qqQQ", none(), none()),
        ("qqq_QQQ", "qqqQQQ", none(), none()),
        ("nested_balanced", "qqQqQQ", none(), none()),
        ("Q_only", "Q", none(), none()),
        ("QQ_only", "QQ", none(), none()),
        ("q_QQ_unbalanced", "qQQ", none(), none()),
        ("qq_QQQ_unbalanced", "qqQQQ", none(), none()),
        ("qqQQ_then_Q", "qqQQQ", none(), none()),
        ("q_with_operands", "q", some(), none()),
        ("qq_with_operands", "qq", some(), none()),
        ("qQ_with_Q_operands", "qQ", none(), some()),
        ("q_operands_both", "qQ", some(), some()),
        ("round_trip", "qQ", none(), none()),
        ("deep_round_trip", "qqqqQQQQ", none(), none()),
    ]


_IDS = [c[0] for c in _cases()]


def _run_sequence(
    steps: str, q_operands: list[COSBase], big_q_operands: list[COSBase]
) -> str:
    engine = _DepthEngine()
    save = SaveGraphicsState()
    save.set_context(engine)
    restore = RestoreGraphicsState()
    restore.set_context(engine)
    q_op = Operator.get_operator("q")
    big_q_op = Operator.get_operator("Q")
    try:
        for c in steps:
            if c == "q":
                save.process(q_op, q_operands)
            else:
                restore.process(big_q_op, big_q_operands)
    except EmptyGraphicsStackException:
        return f"ERR:EmptyGraphicsStackException@{engine.get_graphics_stack_size()}"
    return str(engine.get_graphics_stack_size())


def _pypdfbox_outcomes() -> dict[str, str]:
    return {
        case_id: _run_sequence(steps, q_ops, big_q_ops)
        for case_id, steps, q_ops, big_q_ops in _cases()
    }


def _parse_java(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        case_id, _, outcome = line.partition("\t")
        result[case_id] = outcome
    return result


@requires_oracle
def test_save_restore_state_fuzz_parity() -> None:
    java = _parse_java(run_probe_text("SaveRestoreStateFuzzProbe"))
    py = _pypdfbox_outcomes()
    assert set(py) == set(java), (
        f"case-id mismatch: py-only={set(py) - set(java)} "
        f"java-only={set(java) - set(py)}"
    )
    diffs = {cid: (java[cid], py[cid]) for cid in java if java[cid] != py[cid]}
    assert not diffs, (
        "q/Q save-restore-state fuzz divergences (java, py):\n"
        + "\n".join(
            f"  {cid}: java={j!r} py={p!r}" for cid, (j, p) in sorted(diffs.items())
        )
    )


def test_q_ignores_operands() -> None:
    """``q`` ignores its operand list (no arity / type guard): a ``q`` with
    extra operands pushes exactly like a bare ``q``."""
    out = _pypdfbox_outcomes()
    assert out["q_only"] == out["q_with_operands"] == "2"
    assert out["qq"] == out["qq_with_operands"] == "3"


def test_Q_throws_on_single_frame_stack() -> None:
    """``Q`` on the seed (size-1) stack raises EmptyGraphicsStackException;
    more restores than saves throws rather than under-flowing."""
    out = _pypdfbox_outcomes()
    assert out["Q_only"] == "ERR:EmptyGraphicsStackException@1"
    assert out["q_QQ_unbalanced"] == "ERR:EmptyGraphicsStackException@1"
    assert out["qqQQ_then_Q"] == "ERR:EmptyGraphicsStackException@1"


def test_balanced_nesting_round_trips() -> None:
    """Balanced q/Q sequences return to the seed depth (1)."""
    out = _pypdfbox_outcomes()
    for cid in ("q_then_Q", "qq_QQ", "nested_balanced", "round_trip", "deep_round_trip"):
        assert out[cid] == "1", cid


def test_Q_ignores_operands() -> None:
    """Operands on ``Q`` are ignored — it still pops normally."""
    out = _pypdfbox_outcomes()
    assert out["qQ_with_Q_operands"] == out["q_operands_both"] == "1"

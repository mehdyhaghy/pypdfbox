"""Wave 1275 — Operator.execute dispatch helper parity."""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator_processor import OperatorProcessor


class _RecordingProcessor(OperatorProcessor):
    """Captures process() calls so the test can assert dispatch."""

    def __init__(self) -> None:
        super().__init__(context=None)
        self.calls: list[tuple[Operator, list[Any]]] = []

    def process(self, operator: Operator, operands: list[Any]) -> None:
        self.calls.append((operator, operands))

    def get_name(self) -> str:
        return "TEST"


def test_execute_uses_attached_operands_when_none_passed() -> None:
    op = Operator.with_operands("Tj", [1, 2, 3])
    proc = _RecordingProcessor()
    op.execute(proc)
    assert len(proc.calls) == 1
    assert proc.calls[0][0] is op
    assert proc.calls[0][1] == [1, 2, 3]


def test_execute_overrides_operands_when_explicit_list_passed() -> None:
    op = Operator.with_operands("Tj", [1])
    proc = _RecordingProcessor()
    op.execute(proc, operands=[42, 43])
    assert proc.calls[0][1] == [42, 43]


def test_execute_with_no_operands_passes_empty_list() -> None:
    op = Operator.get_operator("BT")
    proc = _RecordingProcessor()
    op.execute(proc)
    assert proc.calls[0][1] == []

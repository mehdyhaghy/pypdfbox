from __future__ import annotations

from typing import ClassVar

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    OperatorProcessor,
    PDFStreamEngine,
)
from pypdfbox.cos import COSBase, COSInteger


class _Recorder(OperatorProcessor):
    NAME: ClassVar[str] = "RC"

    def __init__(self, context: PDFStreamEngine | None = None) -> None:
        super().__init__(context)
        self.calls: list[tuple[Operator, list[COSBase]]] = []

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self.calls.append((operator, list(operands)))

    def get_name(self) -> str:
        return self.NAME


def test_default_context_is_none() -> None:
    p = _Recorder()
    assert p._context is None


def test_get_context_raises_when_unbound() -> None:
    p = _Recorder()
    with pytest.raises(RuntimeError):
        p.get_context()


def test_set_context_round_trip() -> None:
    engine = PDFStreamEngine()
    p = _Recorder()
    p.set_context(engine)
    assert p.get_context() is engine


def test_constructor_accepts_context() -> None:
    engine = PDFStreamEngine()
    p = _Recorder(engine)
    assert p.get_context() is engine


def test_check_array_types_class() -> None:
    p = _Recorder()
    nums = [COSInteger.get(1), COSInteger.get(2)]
    assert p.check_array_types_class(nums, COSInteger)
    assert not p.check_array_types_class(nums + [Operator.get_operator("BT")], COSInteger)


def test_missing_operand_exception_message_format() -> None:
    op = Operator.get_operator("Tj")
    operands: list[COSBase] = []
    exc = MissingOperandException(op, operands)
    # Mirrors upstream verbatim: "Operator <name> has too few operands: <list>"
    assert str(exc) == "Operator Tj has too few operands: []"
    assert isinstance(exc, OSError)
    assert exc.operator is op
    assert exc.operands is operands


def test_cannot_instantiate_abstract() -> None:
    with pytest.raises(TypeError):
        OperatorProcessor()  # type: ignore[abstract]

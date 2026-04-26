from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import MoveText
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.move: tuple[float, float] | None = None

    def move_text_position(self, tx: float, ty: float) -> None:
        self.move = (tx, ty)


def _bind(processor: MoveText) -> _Spy:
    engine = _Spy()
    engine.add_operator(processor)
    return engine


def test_get_name() -> None:
    assert MoveText().get_name() == "Td"


def test_process_dispatches_floats() -> None:
    p = MoveText()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Td"),
        [COSInteger.get(50), COSFloat(75.5)],
    )
    assert engine.move == (50.0, 75.5)


def test_too_few_operands_raises() -> None:
    p = MoveText()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Td"), [COSInteger.get(1)])


def test_wrong_type_silently_drops() -> None:
    p = MoveText()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Td"),
        [COSString(b"x"), COSInteger.get(2)],
    )
    assert engine.move is None

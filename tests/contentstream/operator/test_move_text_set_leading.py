from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import MoveText, MoveTextSetLeading
from pypdfbox.cos import COSFloat, COSInteger


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.leading: float | None = None
        self.move: tuple[float, float] | None = None

    def set_text_leading(self, leading: float) -> None:
        self.leading = leading

    def move_text_position(self, tx: float, ty: float) -> None:
        self.move = (tx, ty)


def test_get_name() -> None:
    assert MoveTextSetLeading().get_name() == "TD"


def test_process_sets_negative_leading_then_moves() -> None:
    engine = _Spy()
    engine.add_operator(MoveText())
    p = MoveTextSetLeading()
    engine.add_operator(p)
    p.process(
        Operator.get_operator("TD"),
        [COSInteger.get(10), COSFloat(15.0)],
    )
    assert engine.leading == -15.0
    assert engine.move == (10.0, 15.0)


def test_too_few_operands_raises() -> None:
    engine = _Spy()
    engine.add_operator(MoveText())
    p = MoveTextSetLeading()
    engine.add_operator(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("TD"), [COSInteger.get(1)])

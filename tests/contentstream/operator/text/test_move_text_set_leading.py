from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import (
    MoveText,
    MoveTextSetLeading,
)
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.move_calls: list[tuple[float, float]] = []
        self.leading_calls: list[float] = []

    def move_text_position(self, tx: float, ty: float) -> None:
        self.move_calls.append((tx, ty))

    def set_text_leading(self, leading: float) -> None:
        self.leading_calls.append(leading)


def _bind() -> tuple[MoveTextSetLeading, _Spy]:
    p = MoveTextSetLeading()
    engine = _Spy()
    engine.add_operator(p)
    engine.add_operator(MoveText())
    return p, engine


def test_get_name() -> None:
    assert MoveTextSetLeading().get_name() == "TD"


def test_process_decomposes_to_set_leading_then_move_text() -> None:
    """``tx ty TD`` must invoke ``set_text_leading(-ty)`` and then
    ``move_text_position(tx, ty)``."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("TD"), [COSFloat(5.0), COSFloat(-12.5)]
    )
    assert engine.leading_calls == [12.5]
    assert engine.move_calls == [(5.0, -12.5)]


def test_process_accepts_cos_integer_operands() -> None:
    p, engine = _bind()
    p.process(
        Operator.get_operator("TD"), [COSInteger.get(2), COSInteger.get(-3)]
    )
    assert engine.leading_calls == [3.0]
    assert engine.move_calls == [(2.0, -3.0)]


def test_zero_operands_raises() -> None:
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("TD"), [])


def test_one_operand_raises() -> None:
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("TD"), [COSFloat(1.0)])


def test_non_number_second_operand_silently_drops() -> None:
    p, engine = _bind()
    p.process(
        Operator.get_operator("TD"), [COSFloat(1.0), COSString(b"oops")]
    )
    assert engine.leading_calls == []
    assert engine.move_calls == []


def test_set_text_leading_observed_even_without_registered_handler() -> None:
    """The engine notification fires directly, so subclasses see leading
    even when no SET_TEXT_LEADING operator has been registered."""
    p = MoveTextSetLeading()
    engine = _Spy()
    engine.add_operator(p)
    engine.add_operator(MoveText())
    p.process(
        Operator.get_operator("TD"), [COSFloat(0.0), COSFloat(-7.0)]
    )
    assert engine.leading_calls == [7.0]


def test_re_export_canonical() -> None:
    from pypdfbox.contentstream.operator.text import (
        MoveTextSetLeading as Reexport,
    )

    assert Reexport is MoveTextSetLeading

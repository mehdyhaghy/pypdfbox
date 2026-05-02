from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream import OperatorName
from pypdfbox.contentstream.operator.text import (
    MoveText,
    MoveTextSetLeading,
    SetTextLeading,
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


def test_get_name_matches_operator_name_constant() -> None:
    """``get_name()`` must return :data:`OperatorName.MOVE_TEXT_SET_LEADING`
    (not a magic string literal) — guards against drift between the
    constant table and the operator handler."""
    assert (
        MoveTextSetLeading().get_name()
        == OperatorName.MOVE_TEXT_SET_LEADING
        == "TD"
    )


def test_leading_fires_only_once_when_tl_handler_registered() -> None:
    """When a ``TL`` handler is registered, ``TD`` must dispatch via the
    synthetic ``TL`` op only — no double notification via direct engine
    call. Mirrors upstream which solely uses ``processOperator``."""
    p = MoveTextSetLeading()
    engine = _Spy()
    engine.add_operator(p)
    engine.add_operator(SetTextLeading())
    engine.add_operator(MoveText())
    p.process(
        Operator.get_operator("TD"), [COSFloat(0.0), COSFloat(-9.0)]
    )
    assert engine.leading_calls == [9.0]  # exactly one notification


def test_leading_falls_back_to_direct_when_no_tl_handler() -> None:
    """No ``TL`` handler registered → fall back to direct engine
    notification so subclasses still observe the leading change."""
    p = MoveTextSetLeading()
    engine = _Spy()
    engine.add_operator(p)
    engine.add_operator(MoveText())  # no SetTextLeading registered
    p.process(
        Operator.get_operator("TD"), [COSFloat(0.0), COSFloat(-4.0)]
    )
    assert engine.leading_calls == [4.0]


def test_negative_zero_ty() -> None:
    """``-(-0.0) == 0.0`` — the leading must be the IEEE-754 ``+0.0``."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("TD"), [COSFloat(0.0), COSFloat(-0.0)]
    )
    assert engine.leading_calls == [0.0]
    # No surprises for the move either.
    assert engine.move_calls == [(0.0, -0.0)]


def test_non_number_first_operand_still_sets_leading() -> None:
    """Upstream only validates ``arguments.get(1)`` — the first operand
    being non-number doesn't short-circuit. The leading is set, then
    ``MoveText`` silently drops the non-number.
    """
    p, engine = _bind()
    p.process(
        Operator.get_operator("TD"),
        [COSString(b"oops"), COSFloat(-6.0)],
    )
    assert engine.leading_calls == [6.0]
    assert engine.move_calls == []  # MoveText silently dropped


def test_extra_operands_ignored() -> None:
    """Extra operands beyond the second are passed through verbatim to
    the inner ``Td`` (which only consumes its first two). The leading
    is still set from operand[1]."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("TD"),
        [COSFloat(1.0), COSFloat(-2.0), COSFloat(99.0)],
    )
    assert engine.leading_calls == [2.0]
    assert engine.move_calls == [(1.0, -2.0)]

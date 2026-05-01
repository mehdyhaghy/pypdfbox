from __future__ import annotations

import logging

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
        self.calls: list[tuple[float, float]] = []

    def move_text_position(self, tx: float, ty: float) -> None:
        self.calls.append((tx, ty))


def _bind() -> tuple[MoveText, _Spy]:
    p = MoveText()
    engine = _Spy()
    engine.add_operator(p)
    return p, engine


def test_get_name() -> None:
    assert MoveText().get_name() == "Td"


def test_process_dispatches_floats() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Td"), [COSFloat(10.0), COSFloat(-20.5)])
    assert engine.calls == [(10.0, -20.5)]


def test_process_accepts_cos_integer_operands() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Td"), [COSInteger.get(3), COSInteger.get(4)])
    assert engine.calls == [(3.0, 4.0)]


def test_zero_operands_raises() -> None:
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Td"), [])


def test_one_operand_raises() -> None:
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Td"), [COSFloat(1.0)])


def test_non_number_first_operand_silently_drops() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Td"), [COSString(b"x"), COSFloat(1.0)])
    assert engine.calls == []


def test_non_number_second_operand_silently_drops() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Td"), [COSFloat(1.0), COSString(b"y")])
    assert engine.calls == []


def test_extra_operands_are_ignored() -> None:
    p, engine = _bind()
    p.process(
        Operator.get_operator("Td"),
        [COSFloat(1.0), COSFloat(2.0), COSFloat(99.0)],
    )
    assert engine.calls == [(1.0, 2.0)]


# ---- text-line-matrix null guard (parity with upstream LOG.warn) ----


class _TrackingEngine(PDFStreamEngine):
    """Subclass that overrides ``get_text_line_matrix`` — opting into
    the upstream null-guard. Returning ``None`` simulates a Td that
    landed outside a BT/ET pair."""

    def __init__(self, line_matrix: object) -> None:
        super().__init__()
        self._lm: object = line_matrix
        self.calls: list[tuple[float, float]] = []

    def get_text_line_matrix(self) -> object:
        return self._lm

    def move_text_position(self, tx: float, ty: float) -> None:
        self.calls.append((tx, ty))


def test_guard_skips_when_subclass_text_line_matrix_is_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    p = MoveText()
    engine = _TrackingEngine(line_matrix=None)
    engine.add_operator(p)
    with caplog.at_level(logging.WARNING):
        p.process(Operator.get_operator("Td"), [COSFloat(1.0), COSFloat(2.0)])
    assert engine.calls == []
    assert any("TextLineMatrix is null" in rec.message for rec in caplog.records)


def test_guard_passes_when_subclass_text_line_matrix_is_not_none() -> None:
    p = MoveText()
    engine = _TrackingEngine(line_matrix=object())
    engine.add_operator(p)
    p.process(Operator.get_operator("Td"), [COSFloat(1.0), COSFloat(2.0)])
    assert engine.calls == [(1.0, 2.0)]


def test_guard_inert_for_base_engine_default_none() -> None:
    """Base ``PDFStreamEngine.get_text_line_matrix`` returns ``None`` but
    we still pass the op through (the subclass hasn't opted in)."""
    p, engine = _bind()
    p.process(Operator.get_operator("Td"), [COSFloat(1.0), COSFloat(2.0)])
    assert engine.calls == [(1.0, 2.0)]


def test_re_export_canonical() -> None:
    from pypdfbox.contentstream.operator.text import MoveText as Reexport

    assert Reexport is MoveText

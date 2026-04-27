from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetTextLeading
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.leading: float | None = None
        self.calls: int = 0

    def set_text_leading(self, leading: float) -> None:
        self.leading = leading
        self.calls += 1


def _bind(p: SetTextLeading) -> _Spy:
    engine = _Spy()
    engine.add_operator(p)
    return engine


def test_get_name() -> None:
    assert SetTextLeading().get_name() == "TL"


def test_process_dispatches_with_float() -> None:
    p = SetTextLeading()
    engine = _bind(p)
    p.process(Operator.get_operator("TL"), [COSFloat(14.0)])
    assert engine.leading == 14.0
    assert engine.calls == 1


def test_process_accepts_cos_integer() -> None:
    p = SetTextLeading()
    engine = _bind(p)
    p.process(Operator.get_operator("TL"), [COSInteger.get(12)])
    assert engine.leading == 12.0


def test_process_accepts_negative_leading() -> None:
    p = SetTextLeading()
    engine = _bind(p)
    p.process(Operator.get_operator("TL"), [COSFloat(-5.0)])
    assert engine.leading == -5.0


def test_zero_operands_raises() -> None:
    p = SetTextLeading()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("TL"), [])


def test_wrong_type_silently_drops() -> None:
    p = SetTextLeading()
    engine = _bind(p)
    p.process(Operator.get_operator("TL"), [COSString(b"x")])
    assert engine.leading is None
    assert engine.calls == 0

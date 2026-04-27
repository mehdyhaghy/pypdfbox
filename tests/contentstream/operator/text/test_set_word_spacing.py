from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetWordSpacing
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.spacing: float | None = None
        self.calls: int = 0

    def set_word_spacing(self, spacing: float) -> None:
        self.spacing = spacing
        self.calls += 1


def _bind(p: SetWordSpacing) -> _Spy:
    engine = _Spy()
    engine.add_operator(p)
    return engine


def test_get_name() -> None:
    assert SetWordSpacing().get_name() == "Tw"


def test_process_dispatches_with_float() -> None:
    p = SetWordSpacing()
    engine = _bind(p)
    p.process(Operator.get_operator("Tw"), [COSFloat(1.5)])
    assert engine.spacing == 1.5
    assert engine.calls == 1


def test_process_accepts_cos_integer() -> None:
    p = SetWordSpacing()
    engine = _bind(p)
    p.process(Operator.get_operator("Tw"), [COSInteger.get(3)])
    assert engine.spacing == 3.0


def test_zero_operands_raises() -> None:
    p = SetWordSpacing()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tw"), [])


def test_wrong_type_silently_drops() -> None:
    p = SetWordSpacing()
    engine = _bind(p)
    p.process(Operator.get_operator("Tw"), [COSString(b"x")])
    assert engine.spacing is None
    assert engine.calls == 0

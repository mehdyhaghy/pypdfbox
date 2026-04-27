from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetTextRenderingMode
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.mode: int | None = None
        self.calls: int = 0

    def set_text_rendering_mode(self, mode: int) -> None:
        self.mode = mode
        self.calls += 1


class _BaseSpy(PDFStreamEngine):
    """No notifier override — exercises the missing-notifier branch."""


def test_get_name() -> None:
    assert SetTextRenderingMode().get_name() == "Tr"


def test_process_dispatches_int_mode() -> None:
    p = SetTextRenderingMode()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Tr"), [COSInteger.get(2)])
    assert engine.mode == 2
    assert engine.calls == 1


def test_process_accepts_cos_float_int_value() -> None:
    """COSNumber.int_value() truncates floats — verifies dispatch path."""
    p = SetTextRenderingMode()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Tr"), [COSFloat(3.0)])
    assert engine.mode == 3


def test_process_no_op_when_engine_lacks_notifier() -> None:
    p = SetTextRenderingMode()
    engine = _BaseSpy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Tr"), [COSInteger.get(0)])


def test_zero_operands_raises() -> None:
    p = SetTextRenderingMode()
    engine = _Spy()
    engine.add_operator(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tr"), [])


def test_wrong_type_silently_drops() -> None:
    p = SetTextRenderingMode()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Tr"), [COSString(b"x")])
    assert engine.mode is None
    assert engine.calls == 0

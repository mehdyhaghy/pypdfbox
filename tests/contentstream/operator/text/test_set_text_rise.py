from __future__ import annotations

from pypdfbox.contentstream import (
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetTextRise
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.rise: float | None = None
        self.calls: int = 0

    def set_text_rise(self, rise: float) -> None:
        self.rise = rise
        self.calls += 1


class _BaseSpy(PDFStreamEngine):
    """No notifier override — exercises the missing-notifier branch."""


def test_get_name() -> None:
    assert SetTextRise().get_name() == "Ts"


def test_process_dispatches_float_rise() -> None:
    p = SetTextRise()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Ts"), [COSFloat(3.5)])
    assert engine.rise == 3.5
    assert engine.calls == 1


def test_process_accepts_negative_rise_for_subscript() -> None:
    p = SetTextRise()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Ts"), [COSFloat(-2.0)])
    assert engine.rise == -2.0


def test_process_accepts_cos_integer() -> None:
    p = SetTextRise()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Ts"), [COSInteger.get(4)])
    assert engine.rise == 4.0


def test_process_no_op_when_engine_lacks_notifier() -> None:
    p = SetTextRise()
    engine = _BaseSpy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Ts"), [COSFloat(1.0)])


def test_zero_operands_silently_returns() -> None:
    """Upstream `SetTextRise.process` returns silently on empty args."""
    p = SetTextRise()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Ts"), [])
    assert engine.rise is None
    assert engine.calls == 0


def test_wrong_type_silently_drops() -> None:
    p = SetTextRise()
    engine = _Spy()
    engine.add_operator(p)
    p.process(Operator.get_operator("Ts"), [COSString(b"x")])
    assert engine.rise is None
    assert engine.calls == 0

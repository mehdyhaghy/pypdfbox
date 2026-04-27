from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetHorizontalTextScaling
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.scale: float | None = None
        self.calls: int = 0

    def set_horizontal_scaling(self, scale: float) -> None:
        self.scale = scale
        self.calls += 1


class _BaseSpy(PDFStreamEngine):
    """No ``set_horizontal_scaling`` override — exercises the missing-
    notifier branch."""


def _bind(p: SetHorizontalTextScaling, engine: PDFStreamEngine) -> None:
    engine.add_operator(p)


def test_get_name() -> None:
    assert SetHorizontalTextScaling().get_name() == "Tz"


def test_process_dispatches_when_engine_overrides() -> None:
    p = SetHorizontalTextScaling()
    engine = _Spy()
    _bind(p, engine)
    p.process(Operator.get_operator("Tz"), [COSInteger.get(100)])
    assert engine.scale == 100.0
    assert engine.calls == 1


def test_process_accepts_cos_float() -> None:
    p = SetHorizontalTextScaling()
    engine = _Spy()
    _bind(p, engine)
    p.process(Operator.get_operator("Tz"), [COSFloat(75.5)])
    assert engine.scale == 75.5


def test_process_no_op_when_engine_lacks_notifier() -> None:
    """Cluster #2 base engine has no ``set_horizontal_scaling`` — must
    silently no-op rather than blow up."""
    p = SetHorizontalTextScaling()
    engine = _BaseSpy()
    _bind(p, engine)
    p.process(Operator.get_operator("Tz"), [COSFloat(50.0)])
    # nothing to assert beyond "did not raise"


def test_zero_operands_raises() -> None:
    p = SetHorizontalTextScaling()
    engine = _Spy()
    _bind(p, engine)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tz"), [])


def test_wrong_type_silently_drops() -> None:
    p = SetHorizontalTextScaling()
    engine = _Spy()
    _bind(p, engine)
    p.process(Operator.get_operator("Tz"), [COSString(b"x")])
    assert engine.scale is None
    assert engine.calls == 0

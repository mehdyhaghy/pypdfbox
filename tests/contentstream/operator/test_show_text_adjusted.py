from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import ShowTextAdjusted
from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.array: COSArray | None = None

    def show_text_strings(self, array: COSArray) -> None:
        self.array = array


def _bind(processor: ShowTextAdjusted) -> _Spy:
    engine = _Spy()
    engine.add_operator(processor)
    return engine


def test_get_name() -> None:
    assert ShowTextAdjusted().get_name() == "TJ"


def test_process_forwards_array() -> None:
    p = ShowTextAdjusted()
    engine = _bind(p)
    array = COSArray()
    array.add(COSString(b"hi"))
    array.add(COSFloat(-120.0))
    p.process(Operator.get_operator("TJ"), [array])
    assert engine.array is array


def test_zero_operands_raises() -> None:
    p = ShowTextAdjusted()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("TJ"), [])


def test_wrong_type_silently_drops() -> None:
    p = ShowTextAdjusted()
    engine = _bind(p)
    p.process(Operator.get_operator("TJ"), [COSInteger.get(1)])
    assert engine.array is None

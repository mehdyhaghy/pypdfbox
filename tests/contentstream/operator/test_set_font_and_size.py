from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetFontAndSize
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.font: tuple[COSName, float] | None = None

    def set_font(self, font_name: COSName, font_size: float) -> None:
        self.font = (font_name, font_size)


def _bind(processor: SetFontAndSize) -> _Spy:
    engine = _Spy()
    engine.add_operator(processor)
    return engine


def test_get_name() -> None:
    assert SetFontAndSize().get_name() == "Tf"


def test_process_dispatches_with_float_size() -> None:
    p = SetFontAndSize()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSInteger.get(12)],
    )
    assert engine.font == (COSName.get_pdf_name("F1"), 12.0)


def test_process_accepts_cos_float_size() -> None:
    p = SetFontAndSize()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSFloat(10.5)],
    )
    assert engine.font == (COSName.get_pdf_name("F1"), 10.5)


def test_zero_operands_raises() -> None:
    p = SetFontAndSize()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tf"), [])


def test_one_operand_raises() -> None:
    p = SetFontAndSize()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tf"), [COSName.get_pdf_name("F1")])


def test_wrong_first_type_silently_drops() -> None:
    p = SetFontAndSize()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Tf"),
        [COSString(b"F1"), COSInteger.get(12)],
    )
    assert engine.font is None


def test_wrong_second_type_silently_drops() -> None:
    p = SetFontAndSize()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSString(b"12")],
    )
    assert engine.font is None

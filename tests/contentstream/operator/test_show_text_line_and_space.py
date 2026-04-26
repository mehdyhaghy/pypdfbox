from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import (
    ShowText,
    ShowTextLine,
    ShowTextLineAndSpace,
)
from pypdfbox.cos import COSBase, COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.shown: bytes | None = None
        self.unsupported: list[tuple[str, list[COSBase]]] = []

    def show_text_string(self, text: bytes) -> None:
        self.shown = text

    def unsupported_operator(self, operator: Operator, operands: list[COSBase]) -> None:
        self.unsupported.append((operator.get_name(), list(operands)))


def test_get_name() -> None:
    assert ShowTextLineAndSpace().get_name() == '"'


def test_process_decomposes_to_tw_tc_quote() -> None:
    engine = _Spy()
    engine.add_operator(ShowText())
    engine.add_operator(ShowTextLine())
    p = ShowTextLineAndSpace()
    engine.add_operator(p)
    p.process(
        Operator.get_operator('"'),
        [COSInteger.get(1), COSFloat(2.0), COSString(b"hi")],
    )
    names = [n for n, _ in engine.unsupported]
    assert "Tw" in names
    assert "Tc" in names
    # T* is unsupported too because we didn't register a NEXT_LINE handler.
    assert "T*" in names
    assert engine.shown == b"hi"


def test_too_few_operands_raises() -> None:
    p = ShowTextLineAndSpace()
    engine = _Spy()
    engine.add_operator(p)
    with pytest.raises(MissingOperandException):
        p.process(
            Operator.get_operator('"'),
            [COSInteger.get(1), COSInteger.get(2)],
        )

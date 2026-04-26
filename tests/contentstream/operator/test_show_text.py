from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import ShowText
from pypdfbox.cos import COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.shown: bytes | None = None

    def show_text_string(self, text: bytes) -> None:
        self.shown = text


def _bind(processor: ShowText) -> _Spy:
    engine = _Spy()
    engine.add_operator(processor)
    return engine


def test_get_name() -> None:
    assert ShowText().get_name() == "Tj"


def test_process_passes_bytes() -> None:
    p = ShowText()
    engine = _bind(p)
    p.process(Operator.get_operator("Tj"), [COSString(b"Hello")])
    assert engine.shown == b"Hello"


def test_zero_operands_raises() -> None:
    p = ShowText()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tj"), [])


def test_wrong_type_silently_drops() -> None:
    p = ShowText()
    engine = _bind(p)
    p.process(Operator.get_operator("Tj"), [COSInteger.get(42)])
    assert engine.shown is None

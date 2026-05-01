from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    OperatorName,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import ShowText
from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.shown: bytes | None = None
        self.call_count: int = 0

    def show_text_string(self, text: bytes) -> None:
        self.shown = text
        self.call_count += 1


def _bind(processor: ShowText) -> _Spy:
    engine = _Spy()
    engine.add_operator(processor)
    return engine


def test_get_name() -> None:
    assert ShowText().get_name() == "Tj"


def test_get_name_matches_operator_name_constant() -> None:
    assert ShowText().get_name() == OperatorName.SHOW_TEXT


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


def test_zero_operands_message_carries_operator_name_and_operands() -> None:
    """``MissingOperandException`` mirrors upstream's verbatim message."""
    p = ShowText()
    _bind(p)
    op = Operator.get_operator("Tj")
    with pytest.raises(MissingOperandException) as exc_info:
        p.process(op, [])
    msg = str(exc_info.value)
    assert "Tj" in msg
    assert "too few operands" in msg
    # Verify the carried operands list is the empty list we passed in.
    assert exc_info.value.operands == []
    assert exc_info.value.operator is op


def test_wrong_type_silently_drops() -> None:
    p = ShowText()
    engine = _bind(p)
    p.process(Operator.get_operator("Tj"), [COSInteger.get(42)])
    assert engine.shown is None
    assert engine.call_count == 0


def test_wrong_type_cos_array_silently_drops() -> None:
    """A ``COSArray`` first operand (a TJ-shaped operand on Tj) is dropped."""
    p = ShowText()
    engine = _bind(p)
    arr = COSArray()
    arr.add(COSString(b"oops"))
    p.process(Operator.get_operator("Tj"), [arr])
    assert engine.shown is None


def test_wrong_type_cos_name_silently_drops() -> None:
    p = ShowText()
    engine = _bind(p)
    p.process(Operator.get_operator("Tj"), [COSName.get_pdf_name("F1")])
    assert engine.shown is None


def test_empty_string_passes_through() -> None:
    """Mirrors upstream's ``( )Tj`` ignore comment — but pypdfbox does
    actually forward an empty bytes payload (the upstream comment refers
    to the ``arguments.isEmpty()`` operand-stack check, not an empty
    ``COSString``). An empty string is still a syntactically valid
    operand and reaches :meth:`show_text_string`."""
    p = ShowText()
    engine = _bind(p)
    p.process(Operator.get_operator("Tj"), [COSString(b"")])
    assert engine.shown == b""
    assert engine.call_count == 1


def test_extra_operands_are_ignored() -> None:
    """Upstream only consults ``arguments.get(0)``."""
    p = ShowText()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Tj"),
        [COSString(b"first"), COSString(b"second"), COSFloat(3.14)],
    )
    assert engine.shown == b"first"
    assert engine.call_count == 1


def test_get_context_unbound_raises() -> None:
    """Calling ``process`` before registration raises ``RuntimeError``
    via :meth:`OperatorProcessor.get_context`. Defensive deviation from
    upstream (which would NPE on ``getContext().showTextString(...)``)."""
    p = ShowText()
    with pytest.raises(RuntimeError):
        p.process(Operator.get_operator("Tj"), [COSString(b"x")])

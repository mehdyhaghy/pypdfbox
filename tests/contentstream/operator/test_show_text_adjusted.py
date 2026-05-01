from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    OperatorName,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import ShowTextAdjusted
from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.array: COSArray | None = None
        self.call_count: int = 0

    def show_text_strings(self, array: COSArray) -> None:
        self.array = array
        self.call_count += 1


def _bind(processor: ShowTextAdjusted) -> _Spy:
    engine = _Spy()
    engine.add_operator(processor)
    return engine


def test_get_name() -> None:
    assert ShowTextAdjusted().get_name() == "TJ"


def test_get_name_matches_operator_name_constant() -> None:
    assert ShowTextAdjusted().get_name() == OperatorName.SHOW_TEXT_ADJUSTED


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


def test_zero_operands_message_carries_operator_name_and_operands() -> None:
    p = ShowTextAdjusted()
    _bind(p)
    op = Operator.get_operator("TJ")
    with pytest.raises(MissingOperandException) as exc_info:
        p.process(op, [])
    msg = str(exc_info.value)
    assert "TJ" in msg
    assert "too few operands" in msg
    assert exc_info.value.operands == []
    assert exc_info.value.operator is op


def test_wrong_type_silently_drops() -> None:
    p = ShowTextAdjusted()
    engine = _bind(p)
    p.process(Operator.get_operator("TJ"), [COSInteger.get(1)])
    assert engine.array is None
    assert engine.call_count == 0


def test_wrong_type_cos_string_silently_drops() -> None:
    """A bare ``COSString`` (a Tj-shaped operand on TJ) is dropped."""
    p = ShowTextAdjusted()
    engine = _bind(p)
    p.process(Operator.get_operator("TJ"), [COSString(b"oops")])
    assert engine.array is None


def test_wrong_type_cos_name_silently_drops() -> None:
    p = ShowTextAdjusted()
    engine = _bind(p)
    p.process(Operator.get_operator("TJ"), [COSName.get_pdf_name("X")])
    assert engine.array is None


def test_empty_array_forwards_through() -> None:
    """Empty ``[]`` is still a valid (if degenerate) ``TJ`` operand and
    reaches :meth:`show_text_strings` — only the operand-stack-empty
    case short-circuits."""
    p = ShowTextAdjusted()
    engine = _bind(p)
    empty = COSArray()
    p.process(Operator.get_operator("TJ"), [empty])
    assert engine.array is empty
    assert engine.call_count == 1


def test_mixed_array_forwarded_unchanged() -> None:
    """A TJ array with strings, integers and floats is forwarded as-is —
    decoding/iteration is the engine's responsibility."""
    p = ShowTextAdjusted()
    engine = _bind(p)
    arr = COSArray()
    arr.add(COSString(b"He"))
    arr.add(COSInteger.get(-50))
    arr.add(COSString(b"llo"))
    arr.add(COSFloat(120.5))
    p.process(Operator.get_operator("TJ"), [arr])
    assert engine.array is arr
    # Engine receives the *same* array reference (no copy) so subclasses
    # are free to walk it without re-allocating.
    assert engine.array.size() == 4


def test_extra_operands_are_ignored() -> None:
    """Upstream only consults ``arguments.get(0)``."""
    p = ShowTextAdjusted()
    engine = _bind(p)
    primary = COSArray()
    primary.add(COSString(b"primary"))
    spurious = COSArray()
    spurious.add(COSString(b"spurious"))
    p.process(Operator.get_operator("TJ"), [primary, spurious, COSFloat(7.0)])
    assert engine.array is primary
    assert engine.call_count == 1


def test_get_context_unbound_raises() -> None:
    """Calling ``process`` before registration raises ``RuntimeError``
    via :meth:`OperatorProcessor.get_context`."""
    p = ShowTextAdjusted()
    arr = COSArray()
    arr.add(COSString(b"x"))
    with pytest.raises(RuntimeError):
        p.process(Operator.get_operator("TJ"), [arr])

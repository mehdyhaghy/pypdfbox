from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    OperatorName,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetFontAndSize
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[COSName, float]] = []

    def set_font(self, font_name: COSName, font_size: float) -> None:
        self.calls.append((font_name, font_size))


def _bind() -> tuple[SetFontAndSize, _Spy]:
    p = SetFontAndSize()
    engine = _Spy()
    engine.add_operator(p)
    return p, engine


def test_get_name() -> None:
    assert SetFontAndSize().get_name() == "Tf"


def test_process_dispatches_name_and_float_size() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Tf"), [COSName.get_pdf_name("F1"), COSFloat(12.0)])
    assert engine.calls == [(COSName.get_pdf_name("F1"), 12.0)]


def test_process_accepts_cos_integer_size() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Tf"), [COSName.get_pdf_name("Helv"), COSInteger.get(10)])
    assert engine.calls == [(COSName.get_pdf_name("Helv"), 10.0)]


def test_zero_operands_raises() -> None:
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tf"), [])


def test_one_operand_raises() -> None:
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tf"), [COSName.get_pdf_name("F1")])


def test_non_name_first_operand_silently_drops() -> None:
    """Mirrors upstream's ``!(base0 instanceof COSName)`` short-circuit."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tf"), [COSString(b"oops"), COSFloat(12.0)]
    )
    assert engine.calls == []


def test_non_number_second_operand_silently_drops() -> None:
    """Mirrors upstream's ``!(base1 instanceof COSNumber)`` short-circuit."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSString(b"oops")],
    )
    assert engine.calls == []


def test_extra_operands_are_ignored() -> None:
    """Upstream only consults the first two operands."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSFloat(8.0), COSFloat(99.0)],
    )
    assert engine.calls == [(COSName.get_pdf_name("F1"), 8.0)]


def test_re_export_canonical() -> None:
    from pypdfbox.contentstream.operator.text import (
        SetFontAndSize as Reexport,
    )

    assert Reexport is SetFontAndSize


def test_get_name_matches_operator_name_constant() -> None:
    assert SetFontAndSize().get_name() == OperatorName.SET_FONT_AND_SIZE


def test_zero_operands_message_carries_operator_name() -> None:
    """``MissingOperandException`` mirrors upstream's verbatim message."""
    p, _ = _bind()
    op = Operator.get_operator("Tf")
    with pytest.raises(MissingOperandException) as exc_info:
        p.process(op, [])
    msg = str(exc_info.value)
    assert "Tf" in msg
    assert "too few operands" in msg
    assert exc_info.value.operator is op
    assert exc_info.value.operands == []


def test_one_operand_message_carries_partial_operands() -> None:
    """The single-operand list is preserved on the exception so callers
    can inspect what was supplied."""
    p, _ = _bind()
    name = COSName.get_pdf_name("F1")
    with pytest.raises(MissingOperandException) as exc_info:
        p.process(Operator.get_operator("Tf"), [name])
    assert exc_info.value.operands == [name]


def test_negative_size_propagates() -> None:
    """A negative ``Tf`` size is unusual but legal at the operator
    level — upstream stores whatever ``floatValue()`` returns. We do
    the same; downstream graphics-state policy decides what to do."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSFloat(-10.0)],
    )
    assert engine.calls == [(COSName.get_pdf_name("F1"), -10.0)]


def test_zero_size_propagates() -> None:
    """A zero ``Tf`` size reaches the engine — no clamping at the
    operator layer (matches upstream)."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSInteger.get(0)],
    )
    assert engine.calls == [(COSName.get_pdf_name("F1"), 0.0)]


def test_get_context_unbound_raises() -> None:
    """Calling ``process`` before registration raises ``RuntimeError``."""
    p = SetFontAndSize()
    with pytest.raises(RuntimeError):
        p.process(
            Operator.get_operator("Tf"),
            [COSName.get_pdf_name("F1"), COSFloat(12.0)],
        )

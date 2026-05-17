"""Coverage-boost tests for ``SetLineDashPattern`` (the older / parallel
``d`` operator processor that lives at
``pypdfbox.contentstream.operator.state.set_line_dash_pattern``).
"""
from __future__ import annotations

import logging

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
    OperatorName,
)
from pypdfbox.contentstream.operator.operator_processor import OperatorProcessor
from pypdfbox.contentstream.operator.state.set_line_dash_pattern import (
    SetLineDashPattern,
)
from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName


class _RecordingContext:
    """Stand-in for a PDFStreamEngine that just records dash-pattern calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[COSArray, int]] = []

    def set_line_dash_pattern(self, array: COSArray, phase: int) -> None:
        self.calls.append((array, phase))


def _make_op() -> Operator:
    return Operator.get_operator(OperatorName.SET_LINE_DASHPATTERN)


def test_class_advertises_d_operator_name() -> None:
    assert SetLineDashPattern.OPERATOR_NAME == "d"
    assert SetLineDashPattern().get_name() == "d"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetLineDashPattern, OperatorProcessor)


def test_process_with_zero_operands_raises_missing() -> None:
    p = SetLineDashPattern()
    with pytest.raises(MissingOperandException):
        p.process(_make_op(), [])


def test_process_with_one_operand_raises_missing() -> None:
    p = SetLineDashPattern()
    with pytest.raises(MissingOperandException):
        p.process(_make_op(), [COSArray()])


def test_process_with_non_array_first_operand_silently_returns() -> None:
    # The ``return`` after the ``isinstance(base0, COSArray)`` check.
    p = SetLineDashPattern()
    p.process(_make_op(), [COSName.get_pdf_name("Bogus"), COSInteger.get(0)])


def test_process_with_non_number_phase_silently_returns() -> None:
    # The ``return`` after the ``isinstance(base1, COSNumber)`` check.
    p = SetLineDashPattern()
    p.process(_make_op(), [COSArray(), COSName.get_pdf_name("Bogus")])


def test_process_with_no_context_short_circuits() -> None:
    # No context set on the processor — the setter lookup is skipped.
    p = SetLineDashPattern()
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSFloat(2.0))
    # Should not raise even though no engine is attached.
    p.process(_make_op(), [array, COSInteger.get(0)])


def test_process_forwards_to_context_setter() -> None:
    ctx = _RecordingContext()
    p = SetLineDashPattern(ctx)
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSFloat(2.0))

    p.process(_make_op(), [array, COSInteger.get(5)])

    assert ctx.calls == [(array, 5)]


def test_process_truncates_float_phase_via_int_value() -> None:
    ctx = _RecordingContext()
    p = SetLineDashPattern(ctx)
    array = COSArray()
    array.add(COSFloat(1.0))

    p.process(_make_op(), [array, COSFloat(2.75)])

    assert ctx.calls == [(array, 2)]


def test_process_with_all_zero_array_loops_to_completion() -> None:
    # All-zero entries: the sanity loop never breaks but also never
    # replaces the array — upstream forwards it as-is.
    ctx = _RecordingContext()
    p = SetLineDashPattern(ctx)
    array = COSArray()
    array.add(COSFloat(0.0))
    array.add(COSInteger.get(0))

    p.process(_make_op(), [array, COSInteger.get(0)])

    [(forwarded, phase)] = ctx.calls
    assert forwarded is array
    assert phase == 0


def test_process_with_non_number_element_replaces_with_empty_array(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the dash array carries a non-COSNumber entry, upstream warns
    and substitutes an empty (solid-line) array.
    """
    ctx = _RecordingContext()
    p = SetLineDashPattern(ctx)
    # Leading zero keeps the loop iterating; the COSName entry then trips
    # the ``else`` branch and the warning + replacement.
    array = COSArray()
    array.add(COSFloat(0.0))
    array.add(COSName.get_pdf_name("Bogus"))

    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.contentstream.operator.state.set_line_dash_pattern",
    ):
        p.process(_make_op(), [array, COSInteger.get(0)])

    [(forwarded, phase)] = ctx.calls
    assert forwarded is not array
    assert isinstance(forwarded, COSArray)
    assert forwarded.size() == 0
    assert phase == 0
    assert any("non number element" in rec.message for rec in caplog.records)


def test_process_with_nonzero_first_entry_breaks_loop_early() -> None:
    """A non-zero numeric entry in the first slot short-circuits the
    sanity loop on the very first iteration — the array passes through
    unmodified.
    """
    ctx = _RecordingContext()
    p = SetLineDashPattern(ctx)
    array = COSArray()
    array.add(COSFloat(5.0))
    array.add(COSName.get_pdf_name("ShouldNotBeChecked"))

    p.process(_make_op(), [array, COSInteger.get(0)])

    [(forwarded, phase)] = ctx.calls
    # Forwarded as-is — loop broke before reaching the COSName.
    assert forwarded is array
    assert phase == 0


def test_process_with_context_lacking_setter_short_circuits() -> None:
    """If ``_context`` is set but doesn't expose ``set_line_dash_pattern``,
    the processor silently does nothing — covers the ``getattr`` ``None``
    branch.
    """

    class _NoSetter:
        pass

    p = SetLineDashPattern(_NoSetter())  # type: ignore[arg-type]
    p.process(_make_op(), [COSArray(), COSInteger.get(0)])
    # Reached this point without raising.


def test_get_name_returns_dashpattern_token() -> None:
    assert SetLineDashPattern().get_name() == OperatorName.SET_LINE_DASHPATTERN

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_dash_pattern import (
    SetDashPattern,
)
from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName


class _DashRecordingEngine(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.line_dash_calls: list[tuple[COSArray, int]] = []

    def set_line_dash_pattern(self, array: COSArray, phase: int) -> None:
        self.line_dash_calls.append((array, phase))


def test_class_advertises_d_operator_name() -> None:
    assert SetDashPattern.OPERATOR_NAME == "d"
    assert SetDashPattern().get_name() == "d"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetDashPattern, OperatorProcessor)


def test_process_with_solid_pattern_does_not_raise() -> None:
    # ``[] 0 d`` — solid line.
    p = SetDashPattern()
    p.process(
        Operator.get_operator("d"), [COSArray(), COSInteger.get(0)]
    )


def test_process_with_dashed_pattern_does_not_raise() -> None:
    # ``[3 2] 0 d`` — 3-on, 2-off pattern.
    p = SetDashPattern()
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSFloat(2.0))
    p.process(
        Operator.get_operator("d"), [array, COSInteger.get(0)]
    )


def test_process_forwards_dash_array_and_phase_to_engine() -> None:
    engine = _DashRecordingEngine()
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSFloat(2.0))
    p = SetDashPattern(engine)

    p.process(Operator.get_operator("d"), [array, COSInteger.get(5)])

    assert engine.line_dash_calls == [(array, 5)]


def test_process_truncates_float_phase_for_engine() -> None:
    engine = _DashRecordingEngine()
    array = COSArray()
    p = SetDashPattern(engine)

    p.process(Operator.get_operator("d"), [array, COSFloat(2.75)])

    assert engine.line_dash_calls == [(array, 2)]


def test_process_replaces_dash_array_with_non_number_as_solid() -> None:
    engine = _DashRecordingEngine()
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSName.get_pdf_name("Bogus"))
    p = SetDashPattern(engine)

    p.process(Operator.get_operator("d"), [array, COSInteger.get(0)])

    [(dash_array, phase)] = engine.line_dash_calls
    assert dash_array is not array
    assert dash_array.is_empty()
    assert phase == 0


def test_process_with_zero_operands_raises_missing_operand() -> None:
    # Upstream throws ``MissingOperandException`` when fewer than two
    # operands are supplied; we mirror that.
    p = SetDashPattern()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("d"), [])


def test_process_with_one_operand_raises_missing_operand() -> None:
    # ``d`` is a two-operand operator (array + phase); a single operand
    # still triggers the size-2 guard.
    p = SetDashPattern()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("d"), [COSArray()])


def test_process_with_non_array_first_operand_silently_returns() -> None:
    # Upstream ``return``s after the ``instanceof COSArray`` check when
    # the first operand is some other COS type.
    p = SetDashPattern()
    p.process(
        Operator.get_operator("d"),
        [COSName.get_pdf_name("Bogus"), COSInteger.get(0)],
    )


def test_process_with_non_number_phase_silently_returns() -> None:
    # Upstream ``return``s after the ``instanceof COSNumber`` check
    # when the phase operand is not a number.
    p = SetDashPattern()
    p.process(
        Operator.get_operator("d"),
        [COSArray(), COSName.get_pdf_name("Bogus")],
    )


def test_default_registry_routes_d_to_set_dash_pattern() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("d")
    assert isinstance(handler, SetDashPattern)
    assert handler.get_name() == "d"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(
        Operator.get_operator("d"), [COSArray(), COSInteger.get(0)]
    )


def test_get_dash_array_returns_leading_array() -> None:
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSFloat(2.0))
    phase = COSInteger.get(0)
    assert SetDashPattern.get_dash_array([array, phase]) is array


def test_get_dash_array_returns_none_for_short_operands() -> None:
    # Both empty and one-operand operand lists return ``None`` — mirrors
    # the size-2 guard in ``process``.
    assert SetDashPattern.get_dash_array([]) is None
    assert SetDashPattern.get_dash_array([COSArray()]) is None


def test_get_dash_array_returns_none_when_first_operand_not_an_array() -> None:
    assert (
        SetDashPattern.get_dash_array(
            [COSName.get_pdf_name("Bogus"), COSInteger.get(0)]
        )
        is None
    )


def test_get_dash_phase_returns_trailing_number() -> None:
    array = COSArray()
    phase = COSInteger.get(5)
    assert SetDashPattern.get_dash_phase([array, phase]) is phase


def test_get_dash_phase_returns_none_for_short_operands() -> None:
    assert SetDashPattern.get_dash_phase([]) is None
    assert SetDashPattern.get_dash_phase([COSArray()]) is None


def test_get_dash_phase_returns_none_when_phase_not_a_number() -> None:
    # Type-guard mirrors the second ``instanceof`` short-circuit.
    assert (
        SetDashPattern.get_dash_phase(
            [COSArray(), COSName.get_pdf_name("Bogus")]
        )
        is None
    )


def test_get_dash_phase_returns_none_when_array_not_an_array() -> None:
    # A bogus first operand poisons the second-operand extraction too —
    # accessor mirrors the leading guard.
    assert (
        SetDashPattern.get_dash_phase(
            [COSName.get_pdf_name("Bogus"), COSInteger.get(0)]
        )
        is None
    )


def test_get_sanitized_dash_array_returns_original_for_numbers() -> None:
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSInteger.get(2))

    assert SetDashPattern.get_sanitized_dash_array(array) is array


def test_get_sanitized_dash_array_returns_empty_for_non_number() -> None:
    array = COSArray()
    array.add(COSFloat(3.0))
    array.add(COSName.get_pdf_name("Bogus"))

    sanitized = SetDashPattern.get_sanitized_dash_array(array)

    assert sanitized is not array
    assert sanitized.is_empty()

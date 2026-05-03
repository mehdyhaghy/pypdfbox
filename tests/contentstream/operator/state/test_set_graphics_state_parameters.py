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
from pypdfbox.contentstream.operator.state.set_graphics_state_parameters import (
    SetGraphicsStateParameters,
)
from pypdfbox.cos import COSInteger, COSName, COSString


def test_class_advertises_gs_operator_name() -> None:
    assert SetGraphicsStateParameters.OPERATOR_NAME == "gs"
    assert SetGraphicsStateParameters().get_name() == "gs"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetGraphicsStateParameters, OperatorProcessor)


def test_process_with_extgstate_name_operand_does_not_raise() -> None:
    # The single operand is an ExtGState name resolved against the
    # current resource dictionary's ``/ExtGState`` map.
    p = SetGraphicsStateParameters()
    p.process(Operator.get_operator("gs"), [COSName.get_pdf_name("GS1")])


def test_process_with_zero_operands_raises_missing_operand() -> None:
    # Upstream throws ``MissingOperandException`` when no operand is
    # supplied; we mirror that.
    p = SetGraphicsStateParameters()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("gs"), [])


def test_process_with_non_name_operand_silently_returns() -> None:
    # Upstream ``return``s after the ``instanceof COSName`` check when
    # the operand is some other COS type — content stream is malformed
    # but execution continues.
    p = SetGraphicsStateParameters()
    p.process(
        Operator.get_operator("gs"),
        [COSString("GS1")],
    )
    p.process(Operator.get_operator("gs"), [COSInteger.get(1)])


def test_default_registry_routes_gs_to_set_graphics_state_parameters() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("gs")
    assert isinstance(handler, SetGraphicsStateParameters)
    assert handler.get_name() == "gs"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(
        Operator.get_operator("gs"), [COSName.get_pdf_name("Default")]
    )


def test_get_state_name_returns_leading_name() -> None:
    name = COSName.get_pdf_name("GS1")
    assert SetGraphicsStateParameters.get_state_name([name]) is name


def test_get_state_name_returns_none_for_empty_operands() -> None:
    assert SetGraphicsStateParameters.get_state_name([]) is None


def test_get_state_name_returns_none_when_first_operand_not_a_name() -> None:
    # The accessor mirrors the silent-skip guard — a non-COSName produces
    # ``None`` rather than raising.
    assert SetGraphicsStateParameters.get_state_name([COSString("GS1")]) is None
    assert (
        SetGraphicsStateParameters.get_state_name([COSInteger.get(1)]) is None
    )


def test_get_state_name_ignores_trailing_operands() -> None:
    # Mirrors upstream's ``arguments.get(0)`` extraction — only the lead
    # operand is consulted.
    name = COSName.get_pdf_name("GS2")
    assert (
        SetGraphicsStateParameters.get_state_name([name, COSInteger.get(99)])
        is name
    )

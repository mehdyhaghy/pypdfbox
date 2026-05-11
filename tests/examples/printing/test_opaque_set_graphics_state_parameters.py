"""Tests for ``pypdfbox.examples.printing.opaque_set_graphics_state_parameters``."""
from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator.operator_processor import OperatorProcessor
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.contentstream.operator_processor import MissingOperandException
from pypdfbox.examples.printing.opaque_set_graphics_state_parameters import (
    OpaqueSetGraphicsStateParameters,
)


def test_subclasses_operator_processor() -> None:
    assert issubclass(OpaqueSetGraphicsStateParameters, OperatorProcessor)


def test_get_name_returns_gs() -> None:
    op = OpaqueSetGraphicsStateParameters(None)
    assert op.get_name() == OperatorName.SET_GRAPHICS_STATE_PARAMS


class _FakeOperator:
    def get_name(self) -> str:
        return "gs"


def test_process_raises_on_empty_arguments() -> None:
    op = OpaqueSetGraphicsStateParameters(None)
    with pytest.raises(MissingOperandException):
        op.process(_FakeOperator(), [])


def test_process_returns_silently_for_non_name_operand() -> None:
    op = OpaqueSetGraphicsStateParameters(None)
    op.process(_FakeOperator(), [object()])

"""Tests for ``pypdfbox.examples.printing.opaque_draw_object``."""
from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator.graphics.graphics_operator_processor import (
    GraphicsOperatorProcessor,
)
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.contentstream.operator_processor import MissingOperandException
from pypdfbox.examples.printing.opaque_draw_object import OpaqueDrawObject


def test_subclasses_graphics_operator_processor() -> None:
    assert issubclass(OpaqueDrawObject, GraphicsOperatorProcessor)


def test_get_name_returns_do() -> None:
    op = OpaqueDrawObject(None)
    assert op.get_name() == OperatorName.DRAW_OBJECT


class _FakeOperator:
    def get_name(self) -> str:
        return "Do"


def test_process_raises_on_empty_operands() -> None:
    op = OpaqueDrawObject(None)
    with pytest.raises(MissingOperandException):
        op.process(_FakeOperator(), [])


def test_process_returns_silently_for_non_name_operand() -> None:
    op = OpaqueDrawObject(None)
    # Non-COSName operand should produce a silent early return,
    # mirroring the Java `instanceof` check (line 131).
    op.process(_FakeOperator(), [object()])

from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_gray import (
    SetStrokingGray,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert SetStrokingGray.OPERATOR_NAME == "G"


def test_get_name_returns_g_upper() -> None:
    assert SetStrokingGray().get_name() == "G"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetStrokingGray, OperatorProcessor)


def test_process_no_raise_with_gray_value() -> None:
    SetStrokingGray().process(
        Operator.get_operator("G"),
        [COSFloat(0.5)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetStrokingGray().process(Operator.get_operator("G"), [])


def test_default_registry_dispatches_g_upper() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("G")
    assert isinstance(handler, SetStrokingGray)
    registry.process(Operator.get_operator("G"), [COSFloat(0.0)])

from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_cmyk import (
    SetStrokingCMYK,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert SetStrokingCMYK.OPERATOR_NAME == "K"


def test_get_name_returns_k_upper() -> None:
    assert SetStrokingCMYK().get_name() == "K"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetStrokingCMYK, OperatorProcessor)


def test_process_no_raise_with_four_components() -> None:
    SetStrokingCMYK().process(
        Operator.get_operator("K"),
        [COSFloat(0.0), COSFloat(1.0), COSFloat(1.0), COSFloat(0.0)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetStrokingCMYK().process(Operator.get_operator("K"), [])


def test_default_registry_dispatches_k_upper() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("K")
    assert isinstance(handler, SetStrokingCMYK)
    registry.process(
        Operator.get_operator("K"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
    )

from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_cmyk import (
    SetNonStrokingCMYK,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert SetNonStrokingCMYK.OPERATOR_NAME == "k"


def test_get_name_returns_k_lower() -> None:
    assert SetNonStrokingCMYK().get_name() == "k"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetNonStrokingCMYK, OperatorProcessor)


def test_process_no_raise_with_four_components() -> None:
    SetNonStrokingCMYK().process(
        Operator.get_operator("k"),
        [COSFloat(0.5), COSFloat(0.5), COSFloat(0.5), COSFloat(0.5)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetNonStrokingCMYK().process(Operator.get_operator("k"), [])


def test_default_registry_dispatches_k_lower() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("k")
    assert isinstance(handler, SetNonStrokingCMYK)
    registry.process(
        Operator.get_operator("k"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0), COSFloat(1.0)],
    )

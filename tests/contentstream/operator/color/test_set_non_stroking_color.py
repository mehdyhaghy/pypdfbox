from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color import (
    SetNonStrokingColor,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert SetNonStrokingColor.OPERATOR_NAME == "sc"


def test_get_name_returns_sc_lower() -> None:
    assert SetNonStrokingColor().get_name() == "sc"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetNonStrokingColor, OperatorProcessor)


def test_process_accepts_one_component_gray_space() -> None:
    SetNonStrokingColor().process(
        Operator.get_operator("sc"), [COSFloat(0.25)]
    )


def test_process_accepts_three_component_rgb_like() -> None:
    SetNonStrokingColor().process(
        Operator.get_operator("sc"),
        [COSFloat(0.4), COSFloat(0.5), COSFloat(0.6)],
    )


def test_process_accepts_four_component_cmyk_like() -> None:
    SetNonStrokingColor().process(
        Operator.get_operator("sc"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetNonStrokingColor().process(Operator.get_operator("sc"), [])


def test_default_registry_dispatches_sc_lower() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("sc")
    assert isinstance(handler, SetNonStrokingColor)
    registry.process(Operator.get_operator("sc"), [COSFloat(0.5)])

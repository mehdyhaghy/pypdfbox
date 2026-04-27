from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_color import (
    SetStrokingColor,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert SetStrokingColor.OPERATOR_NAME == "SC"


def test_get_name_returns_sc_upper() -> None:
    assert SetStrokingColor().get_name() == "SC"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetStrokingColor, OperatorProcessor)


def test_process_accepts_one_component_gray_space() -> None:
    SetStrokingColor().process(
        Operator.get_operator("SC"), [COSFloat(0.42)]
    )


def test_process_accepts_three_component_rgb_like() -> None:
    SetStrokingColor().process(
        Operator.get_operator("SC"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )


def test_process_accepts_four_component_cmyk_like() -> None:
    SetStrokingColor().process(
        Operator.get_operator("SC"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0), COSFloat(1.0)],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetStrokingColor().process(Operator.get_operator("SC"), [])


def test_default_registry_dispatches_sc_upper() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("SC")
    assert isinstance(handler, SetStrokingColor)
    registry.process(Operator.get_operator("SC"), [COSFloat(0.5)])

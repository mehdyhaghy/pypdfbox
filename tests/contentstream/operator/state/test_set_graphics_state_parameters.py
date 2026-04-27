from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_graphics_state_parameters import (
    SetGraphicsStateParameters,
)
from pypdfbox.cos import COSName


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


def test_process_with_zero_operands_does_not_raise() -> None:
    p = SetGraphicsStateParameters()
    p.process(Operator.get_operator("gs"), [])


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

from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_stroking_color_n import (
    SetStrokingColorN,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat, COSName


def test_class_attribute_operator_name() -> None:
    assert SetStrokingColorN.OPERATOR_NAME == "SCN"


def test_get_name_returns_scn_upper() -> None:
    assert SetStrokingColorN().get_name() == "SCN"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetStrokingColorN, OperatorProcessor)


def test_process_accepts_pure_components() -> None:
    SetStrokingColorN().process(
        Operator.get_operator("SCN"),
        [COSFloat(0.5), COSFloat(0.5), COSFloat(0.5)],
    )


def test_process_accepts_components_followed_by_pattern_name() -> None:
    SetStrokingColorN().process(
        Operator.get_operator("SCN"),
        [
            COSFloat(0.1),
            COSFloat(0.2),
            COSFloat(0.3),
            COSName.get_pdf_name("P1"),
        ],
    )


def test_process_accepts_pattern_name_only() -> None:
    SetStrokingColorN().process(
        Operator.get_operator("SCN"),
        [COSName.get_pdf_name("P0")],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetStrokingColorN().process(Operator.get_operator("SCN"), [])


def test_default_registry_dispatches_scn_upper() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("SCN")
    assert isinstance(handler, SetStrokingColorN)
    registry.process(
        Operator.get_operator("SCN"),
        [COSFloat(0.5), COSName.get_pdf_name("P1")],
    )

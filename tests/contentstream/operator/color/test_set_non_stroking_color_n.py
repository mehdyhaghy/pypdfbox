from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color_n import (
    SetNonStrokingColorN,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat, COSName


def test_class_attribute_operator_name() -> None:
    assert SetNonStrokingColorN.OPERATOR_NAME == "scn"


def test_get_name_returns_scn_lower() -> None:
    assert SetNonStrokingColorN().get_name() == "scn"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetNonStrokingColorN, OperatorProcessor)


def test_process_accepts_pure_components() -> None:
    SetNonStrokingColorN().process(
        Operator.get_operator("scn"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )


def test_process_accepts_components_followed_by_pattern_name() -> None:
    SetNonStrokingColorN().process(
        Operator.get_operator("scn"),
        [
            COSFloat(0.4),
            COSFloat(0.5),
            COSName.get_pdf_name("P2"),
        ],
    )


def test_process_accepts_pattern_name_only() -> None:
    SetNonStrokingColorN().process(
        Operator.get_operator("scn"),
        [COSName.get_pdf_name("P0")],
    )


def test_process_no_raise_with_empty_operands() -> None:
    SetNonStrokingColorN().process(Operator.get_operator("scn"), [])


def test_default_registry_dispatches_scn_lower() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("scn")
    assert isinstance(handler, SetNonStrokingColorN)
    registry.process(
        Operator.get_operator("scn"),
        [COSFloat(0.7), COSName.get_pdf_name("P1")],
    )

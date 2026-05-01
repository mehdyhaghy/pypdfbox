from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.graphics import ShadingFill
from pypdfbox.contentstream.operator.graphics.shading_fill import (
    ShadingFill as ShadingFillDirect,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSInteger, COSName, COSString


def test_class_attribute_operator_name() -> None:
    assert ShadingFill.OPERATOR_NAME == "sh"


def test_get_name_returns_sh() -> None:
    assert ShadingFill().get_name() == "sh"


def test_re_export_matches_module_class() -> None:
    assert ShadingFill is ShadingFillDirect


def test_process_with_name_operand_is_noop() -> None:
    handler = ShadingFill()
    handler.process(
        Operator.get_operator("sh"),
        [COSName.get_pdf_name("Sh0")],
    )


def test_process_accepts_alternate_shading_name() -> None:
    handler = ShadingFill()
    handler.process(
        Operator.get_operator("sh"),
        [COSName.get_pdf_name("Shading1")],
    )


def test_process_with_empty_operands_raises_missing_operand() -> None:
    """Mirrors upstream ``ShadingFill.process`` which throws
    ``MissingOperandException`` when ``operands.isEmpty()``."""
    with pytest.raises(MissingOperandException):
        ShadingFill().process(Operator.get_operator("sh"), [])


def test_process_with_non_name_operand_silently_returns() -> None:
    """Upstream raises for non-COSName operand 0; pypdfbox follows the
    leniency precedent of the path operators (``MoveTo``, ``LineTo``,
    ``CurveTo``, ``AppendRectangleToPath``) and silently skips
    type-mismatched operands."""
    ShadingFill().process(
        Operator.get_operator("sh"),
        [COSString("not-a-name")],
    )


def test_process_with_integer_operand_silently_returns() -> None:
    ShadingFill().process(
        Operator.get_operator("sh"),
        [COSInteger.get(3)],
    )


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("sh")
    assert handler is not None
    assert isinstance(handler, ShadingFill)

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.graphics import (
    DrawObject,
    InvokeNamedXObject,
)
from pypdfbox.contentstream.operator.graphics.invoke_named_xobject import (
    InvokeNamedXObject as InvokeNamedXObjectDirect,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSInteger, COSName, COSString


def test_class_attribute_operator_name() -> None:
    assert InvokeNamedXObject.OPERATOR_NAME == "Do"


def test_get_name_returns_do() -> None:
    assert InvokeNamedXObject().get_name() == "Do"


def test_re_export_matches_module_class() -> None:
    assert InvokeNamedXObject is InvokeNamedXObjectDirect


def test_process_with_name_operand_is_noop() -> None:
    handler = InvokeNamedXObject()
    handler.process(
        Operator.get_operator("Do"),
        [COSName.get_pdf_name("Im0")],
    )


def test_process_accepts_form_name_operand() -> None:
    handler = InvokeNamedXObject()
    handler.process(
        Operator.get_operator("Do"),
        [COSName.get_pdf_name("Fm1")],
    )


def test_process_with_empty_operands_raises_missing_operand() -> None:
    """Mirrors upstream ``DrawObject.process`` which throws
    ``MissingOperandException`` when no operands are provided."""
    with pytest.raises(MissingOperandException):
        InvokeNamedXObject().process(Operator.get_operator("Do"), [])


def test_process_with_non_name_operand_silently_returns() -> None:
    """Mirrors upstream's ``if (!(base0 instanceof COSName)) return;``
    early-return — pypdfbox follows the same lenient skip."""
    InvokeNamedXObject().process(
        Operator.get_operator("Do"),
        [COSString("not-a-name")],
    )


def test_process_with_integer_operand_silently_returns() -> None:
    InvokeNamedXObject().process(
        Operator.get_operator("Do"),
        [COSInteger.get(7)],
    )


def test_draw_object_alias_is_invoke_named_xobject() -> None:
    """Upstream-name parity alias: ``DrawObject`` resolves to the same
    concrete class as the descriptive pypdfbox name."""
    assert DrawObject is InvokeNamedXObject


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("Do")
    assert handler is not None
    assert isinstance(handler, InvokeNamedXObject)

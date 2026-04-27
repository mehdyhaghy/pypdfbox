from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.graphics import InvokeNamedXObject
from pypdfbox.contentstream.operator.graphics.invoke_named_xobject import (
    InvokeNamedXObject as InvokeNamedXObjectDirect,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSName


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


def test_process_accepts_empty_operands_list() -> None:
    """Lite stub does not enforce arity; engine layer will."""
    InvokeNamedXObject().process(Operator.get_operator("Do"), [])


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("Do")
    assert handler is not None
    assert isinstance(handler, InvokeNamedXObject)

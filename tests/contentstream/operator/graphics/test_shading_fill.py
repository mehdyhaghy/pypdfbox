from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.graphics import ShadingFill
from pypdfbox.contentstream.operator.graphics.shading_fill import (
    ShadingFill as ShadingFillDirect,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSName


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


def test_process_accepts_empty_operands_list() -> None:
    """Lite stub does not enforce arity; engine layer will."""
    ShadingFill().process(Operator.get_operator("sh"), [])


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("sh")
    assert handler is not None
    assert isinstance(handler, ShadingFill)

"""Parity tests for the registry-stub ``MoveTextSetLeading`` (``TD``).

Targets
``pypdfbox/contentstream/operator/text/move_text_set_leading_handler.py``
— the lite registry-routing scaffold. The engine-coupled variant in
``move_text_set_leading.py`` (which notifies the engine of the new
text leading + line position) is tested separately. Both share the
upstream class name ``MoveTextSetLeading``; the ``_handler`` filename
suffix exists only to avoid colliding with the older module.
"""

from __future__ import annotations

import logging

from pypdfbox.contentstream import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.text.move_text_set_leading import (
    MoveTextSetLeading as EngineCoupledMoveTextSetLeading,
)
from pypdfbox.contentstream.operator.text.move_text_set_leading_handler import (
    MoveTextSetLeading,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName


def test_operator_name_constant_is_capital_td() -> None:
    assert MoveTextSetLeading.OPERATOR_NAME == "TD"


def test_get_name_returns_capital_td() -> None:
    assert MoveTextSetLeading().get_name() == "TD"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(MoveTextSetLeading, OperatorProcessor)


def test_distinct_from_engine_coupled_variant() -> None:
    """Both classes share the upstream name ``MoveTextSetLeading``; the
    lite stub and engine-coupled handler are intentionally different
    classes."""
    assert MoveTextSetLeading is not EngineCoupledMoveTextSetLeading


def test_process_with_two_float_operands_is_silent() -> None:
    """Happy path: ``tx ty TD`` — the lite stub logs and returns."""
    MoveTextSetLeading().process(
        Operator.get_operator("TD"),
        [COSFloat(10.0), COSFloat(-20.0)],
    )


def test_process_with_integer_operands_is_silent() -> None:
    MoveTextSetLeading().process(
        Operator.get_operator("TD"),
        [COSInteger.get(5), COSInteger.get(-15)],
    )


def test_process_with_zero_operands_does_not_raise() -> None:
    MoveTextSetLeading().process(Operator.get_operator("TD"), [])


def test_process_with_single_operand_does_not_raise() -> None:
    """Lite stub does not enforce arity — the rendering-cluster handler
    will raise ``MissingOperandException`` here."""
    MoveTextSetLeading().process(
        Operator.get_operator("TD"), [COSFloat(1.0)]
    )


def test_process_with_wrong_typed_operands_does_not_raise() -> None:
    MoveTextSetLeading().process(
        Operator.get_operator("TD"),
        [COSName.get_pdf_name("X"), COSName.get_pdf_name("Y")],
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    MoveTextSetLeading().process(
        Operator.get_operator("TD"),
        [COSFloat(0.0), COSFloat(-14.0)],
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "MoveTextSetLeading" in m and "TD" in m for m in messages
    )


def test_processor_registered_for_td_capital_in_default_registry() -> None:
    handler = OperatorRegistry().lookup("TD")
    assert isinstance(handler, MoveTextSetLeading)


def test_registry_dispatch_does_not_raise() -> None:
    OperatorRegistry().process(
        Operator.get_operator("TD"),
        [COSFloat(2.5), COSFloat(-12.0)],
    )


def test_get_context_returns_none_for_standalone_use() -> None:
    assert MoveTextSetLeading().get_context() is None

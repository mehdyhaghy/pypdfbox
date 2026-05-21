"""Parity tests for the registry-stub ``SetHorizontalScaling`` (``Tz``).

Targets ``pypdfbox/contentstream/operator/text/set_horizontal_scaling.py``
— the lite registry-routing scaffold. The engine-coupled handler with
the real text-state setter lives in
``set_text_horizontal_scaling.py`` / ``set_horizontal_text_scaling.py``;
this stub mirrors the upstream Java name for the dispatcher.
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
from pypdfbox.contentstream.operator.text.set_horizontal_scaling import (
    SetHorizontalScaling,
)
from pypdfbox.contentstream.operator.text.set_text_horizontal_scaling import (
    SetTextHorizontalScaling,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName


def test_operator_name_constant_is_tz() -> None:
    assert SetHorizontalScaling.OPERATOR_NAME == "Tz"


def test_get_name_returns_tz() -> None:
    assert SetHorizontalScaling().get_name() == "Tz"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(SetHorizontalScaling, OperatorProcessor)


def test_distinct_from_engine_coupled_set_text_horizontal_scaling() -> None:
    """The lite stub and the engine-coupled handler share an operator
    token (``Tz``) but are different classes — keep them decoupled so
    callers can grab the lite scaffold without dragging in the
    text-state setter wiring."""
    assert SetHorizontalScaling is not SetTextHorizontalScaling


def test_process_with_float_operand_is_silent() -> None:
    SetHorizontalScaling().process(
        Operator.get_operator("Tz"), [COSFloat(100.0)]
    )


def test_process_with_integer_operand_is_silent() -> None:
    SetHorizontalScaling().process(
        Operator.get_operator("Tz"), [COSInteger.get(150)]
    )


def test_process_with_empty_operands_does_not_raise() -> None:
    SetHorizontalScaling().process(Operator.get_operator("Tz"), [])


def test_process_with_wrong_typed_operand_does_not_raise() -> None:
    SetHorizontalScaling().process(
        Operator.get_operator("Tz"),
        [COSName.get_pdf_name("Bogus")],
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    SetHorizontalScaling().process(
        Operator.get_operator("Tz"), [COSFloat(110.0)]
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "SetHorizontalScaling" in m and "Tz" in m for m in messages
    )


def test_processor_registered_for_tz_in_default_registry() -> None:
    """The default ``OperatorRegistry`` routes ``Tz`` to the lite stub
    (the engine-coupled variant is wired in by the rendering engine, not
    the standalone registry)."""
    handler = OperatorRegistry().lookup("Tz")
    assert isinstance(handler, SetHorizontalScaling)


def test_registry_dispatch_does_not_raise() -> None:
    OperatorRegistry().process(
        Operator.get_operator("Tz"), [COSFloat(75.0)]
    )


def test_get_context_returns_none_for_standalone_use() -> None:
    assert SetHorizontalScaling().get_context() is None

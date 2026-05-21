"""Parity tests for the registry-stub ``ShowTextArray`` (``TJ``).

Targets ``pypdfbox/contentstream/operator/text/show_text_array.py`` —
the lite registry-routing scaffold. The engine-coupled handler that
forwards to ``show_text_strings`` lives in
``show_text_adjusted.py`` / ``ShowTextAdjusted`` and is tested
separately.
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
from pypdfbox.contentstream.operator.text.show_text_adjusted import (
    ShowTextAdjusted,
)
from pypdfbox.contentstream.operator.text.show_text_array import (
    ShowTextArray,
)
from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSString


def test_operator_name_constant_is_capital_tj() -> None:
    assert ShowTextArray.OPERATOR_NAME == "TJ"


def test_get_name_returns_capital_tj() -> None:
    assert ShowTextArray().get_name() == "TJ"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(ShowTextArray, OperatorProcessor)


def test_distinct_from_engine_coupled_show_text_adjusted() -> None:
    """``ShowTextArray`` (lite) and ``ShowTextAdjusted`` (engine-coupled)
    share the ``TJ`` token; they are intentionally different classes —
    one for standalone routing, the other for the full engine pipeline."""
    assert ShowTextArray is not ShowTextAdjusted


def test_process_with_array_operand_is_silent() -> None:
    """Happy path: ``TJ`` ships a single ``COSArray`` — the lite stub
    logs and returns."""
    arr = COSArray()
    arr.add(COSString(b"Hello"))
    arr.add(COSFloat(-120.0))
    arr.add(COSString(b"World"))
    ShowTextArray().process(Operator.get_operator("TJ"), [arr])


def test_process_with_empty_array_operand_is_silent() -> None:
    ShowTextArray().process(Operator.get_operator("TJ"), [COSArray()])


def test_process_with_zero_operands_does_not_raise() -> None:
    """Lite stub does not enforce arity — the engine-coupled
    ``ShowTextAdjusted`` raises ``MissingOperandException`` for the
    same condition."""
    ShowTextArray().process(Operator.get_operator("TJ"), [])


def test_process_with_wrong_typed_operand_does_not_raise() -> None:
    """A bare ``COSString`` (a Tj-shaped operand on TJ) is logged + dropped
    without raising."""
    ShowTextArray().process(
        Operator.get_operator("TJ"), [COSString(b"oops")]
    )


def test_process_with_extra_operands_does_not_raise() -> None:
    arr = COSArray()
    arr.add(COSString(b"primary"))
    ShowTextArray().process(
        Operator.get_operator("TJ"),
        [arr, COSInteger.get(99), COSName.get_pdf_name("X")],
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    arr = COSArray()
    arr.add(COSString(b"x"))
    ShowTextArray().process(Operator.get_operator("TJ"), [arr])
    messages = [r.getMessage() for r in caplog.records]
    assert any("ShowTextArray" in m and "TJ" in m for m in messages)


def test_processor_registered_for_tj_in_default_registry() -> None:
    handler = OperatorRegistry().lookup("TJ")
    assert isinstance(handler, ShowTextArray)


def test_registry_dispatch_does_not_raise() -> None:
    arr = COSArray()
    arr.add(COSString(b"x"))
    OperatorRegistry().process(Operator.get_operator("TJ"), [arr])


def test_get_context_returns_none_for_standalone_use() -> None:
    assert ShowTextArray().get_context() is None

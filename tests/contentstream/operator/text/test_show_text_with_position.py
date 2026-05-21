"""Parity tests for the registry-stub ``ShowTextWithPosition`` (``'``).

Targets ``pypdfbox/contentstream/operator/text/show_text_with_position.py``
— the lite registry-routing scaffold for the apostrophe operator
(move-to-next-line + show-text). The engine-coupled equivalent
``ShowTextLine`` lives in ``show_text_line.py`` and is tested separately.
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
from pypdfbox.contentstream.operator.text.show_text_line import (
    ShowTextLine,
)
from pypdfbox.contentstream.operator.text.show_text_with_position import (
    ShowTextWithPosition,
)
from pypdfbox.cos import COSInteger, COSName, COSString


def test_operator_name_constant_is_apostrophe() -> None:
    assert ShowTextWithPosition.OPERATOR_NAME == "'"


def test_get_name_returns_apostrophe() -> None:
    assert ShowTextWithPosition().get_name() == "'"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(ShowTextWithPosition, OperatorProcessor)


def test_distinct_from_engine_coupled_show_text_line() -> None:
    """Different classes for the same upstream operator — keep the lite
    registry routing decoupled from the engine-coupled handler."""
    assert ShowTextWithPosition is not ShowTextLine


def test_process_with_cos_string_operand_is_silent() -> None:
    """Happy path: ``'`` ships a single ``COSString`` — the lite stub
    logs and returns."""
    ShowTextWithPosition().process(
        Operator.get_operator("'"), [COSString(b"hello")]
    )


def test_process_with_empty_string_operand_is_silent() -> None:
    ShowTextWithPosition().process(
        Operator.get_operator("'"), [COSString(b"")]
    )


def test_process_with_zero_operands_does_not_raise() -> None:
    """The lite stub does not enforce arity — the rendering-cluster
    handler will raise ``MissingOperandException`` for an empty stack."""
    ShowTextWithPosition().process(Operator.get_operator("'"), [])


def test_process_with_wrong_typed_operand_does_not_raise() -> None:
    ShowTextWithPosition().process(
        Operator.get_operator("'"),
        [COSName.get_pdf_name("Bogus")],
    )


def test_process_with_extra_operands_does_not_raise() -> None:
    ShowTextWithPosition().process(
        Operator.get_operator("'"),
        [COSString(b"primary"), COSInteger.get(7)],
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    ShowTextWithPosition().process(
        Operator.get_operator("'"), [COSString(b"x")]
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "ShowTextWithPosition" in m and "'" in m for m in messages
    )


def test_processor_registered_for_apostrophe_in_default_registry() -> None:
    handler = OperatorRegistry().lookup("'")
    assert isinstance(handler, ShowTextWithPosition)


def test_registry_dispatch_does_not_raise() -> None:
    OperatorRegistry().process(
        Operator.get_operator("'"), [COSString(b"x")]
    )


def test_get_context_returns_none_for_standalone_use() -> None:
    assert ShowTextWithPosition().get_context() is None

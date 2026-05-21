"""Parity tests for the registry-stub ``SetCharacterSpacing`` (``Tc``).

Targets ``pypdfbox/contentstream/operator/text/set_character_spacing.py``
— the lite registry-routing scaffold (text-state bookkeeping arrives
with the rendering cluster).
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
from pypdfbox.contentstream.operator.text.set_character_spacing import (
    SetCharacterSpacing,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName


def test_operator_name_constant_is_tc() -> None:
    assert SetCharacterSpacing.OPERATOR_NAME == "Tc"


def test_get_name_returns_tc() -> None:
    assert SetCharacterSpacing().get_name() == "Tc"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(SetCharacterSpacing, OperatorProcessor)


def test_process_with_float_operand_is_silent() -> None:
    """Happy path: ``Tc`` accepts a single numeric character-spacing
    value — the lite stub logs and returns."""
    SetCharacterSpacing().process(
        Operator.get_operator("Tc"), [COSFloat(0.5)]
    )


def test_process_with_integer_operand_is_silent() -> None:
    SetCharacterSpacing().process(
        Operator.get_operator("Tc"), [COSInteger.get(2)]
    )


def test_process_with_negative_spacing_is_silent() -> None:
    """Character spacing may legitimately be negative — see ISO 32000-1
    §9.3.2 (``Tc`` is a number)."""
    SetCharacterSpacing().process(
        Operator.get_operator("Tc"), [COSFloat(-0.25)]
    )


def test_process_with_empty_operands_does_not_raise() -> None:
    """Lite stub is permissive; the rendering-cluster handler will raise
    ``MissingOperandException`` once arity enforcement lands."""
    SetCharacterSpacing().process(Operator.get_operator("Tc"), [])


def test_process_with_wrong_typed_operand_does_not_raise() -> None:
    SetCharacterSpacing().process(
        Operator.get_operator("Tc"),
        [COSName.get_pdf_name("Bogus")],
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    SetCharacterSpacing().process(
        Operator.get_operator("Tc"), [COSFloat(0.75)]
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "SetCharacterSpacing" in m and "Tc" in m for m in messages
    )


def test_processor_registered_for_tc_in_default_registry() -> None:
    handler = OperatorRegistry().lookup("Tc")
    assert isinstance(handler, SetCharacterSpacing)


def test_registry_dispatch_does_not_raise() -> None:
    OperatorRegistry().process(
        Operator.get_operator("Tc"), [COSFloat(0.1)]
    )


def test_get_context_returns_none_for_standalone_use() -> None:
    assert SetCharacterSpacing().get_context() is None

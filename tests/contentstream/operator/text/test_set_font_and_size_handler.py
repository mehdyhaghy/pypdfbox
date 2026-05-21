"""Parity tests for the registry-stub ``SetFontAndSize`` (``Tf``).

Targets ``pypdfbox/contentstream/operator/text/set_font_and_size_handler.py``
— the lite registry-routing scaffold. The engine-coupled variant in
``set_font_and_size.py`` (which actually notifies the engine of the new
font + size) is tested separately. Both share the upstream class name
``SetFontAndSize``; the ``_handler`` filename suffix exists only to
avoid colliding with the older engine-coupled module.
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
from pypdfbox.contentstream.operator.text.set_font_and_size import (
    SetFontAndSize as EngineCoupledSetFontAndSize,
)
from pypdfbox.contentstream.operator.text.set_font_and_size_handler import (
    SetFontAndSize,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName


def test_operator_name_constant_is_tf() -> None:
    assert SetFontAndSize.OPERATOR_NAME == "Tf"


def test_get_name_returns_tf() -> None:
    assert SetFontAndSize().get_name() == "Tf"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(SetFontAndSize, OperatorProcessor)


def test_distinct_from_engine_coupled_variant() -> None:
    """Both classes share the upstream Java name ``SetFontAndSize``;
    they are intentionally different classes in pypdfbox so the lite
    registry doesn't drag in the engine notification path."""
    assert SetFontAndSize is not EngineCoupledSetFontAndSize


def test_process_with_name_and_size_is_silent() -> None:
    """Happy path: ``/Helv 12 Tf`` — name + number. The lite stub logs
    and returns without raising."""
    SetFontAndSize().process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("Helv"), COSFloat(12.0)],
    )


def test_process_with_integer_size_is_silent() -> None:
    SetFontAndSize().process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSInteger.get(10)],
    )


def test_process_with_zero_operands_does_not_raise() -> None:
    """Lite stub does not enforce arity. The rendering-cluster handler
    raises ``MissingOperandException`` here."""
    SetFontAndSize().process(Operator.get_operator("Tf"), [])


def test_process_with_only_font_name_does_not_raise() -> None:
    SetFontAndSize().process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("Helv")],
    )


def test_process_with_wrong_typed_operands_does_not_raise() -> None:
    """Lite stub is permissive — wrong-typed operands log + return."""
    SetFontAndSize().process(
        Operator.get_operator("Tf"),
        [COSInteger.get(1), COSName.get_pdf_name("Bogus")],
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    SetFontAndSize().process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("Helv"), COSFloat(14.0)],
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "SetFontAndSize" in m and "Tf" in m for m in messages
    )


def test_processor_registered_for_tf_in_default_registry() -> None:
    """The default ``OperatorRegistry`` wires the lite handler — not
    the engine-coupled one — for the standalone routing case."""
    handler = OperatorRegistry().lookup("Tf")
    assert isinstance(handler, SetFontAndSize)


def test_registry_dispatch_does_not_raise() -> None:
    OperatorRegistry().process(
        Operator.get_operator("Tf"),
        [COSName.get_pdf_name("F1"), COSFloat(11.0)],
    )


def test_get_context_returns_none_for_standalone_use() -> None:
    assert SetFontAndSize().get_context() is None

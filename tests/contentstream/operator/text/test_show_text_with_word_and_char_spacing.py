"""Parity tests for ``ShowTextWithWordAndCharSpacing`` (``"``).

Targets ``pypdfbox/contentstream/operator/text/show_text_with_word_and_char_spacing.py``
— the lite registry-routing scaffold for the quotation-mark operator
(set word & char spacing + move to next line + show text). The
engine-coupled equivalent ``ShowTextLineAndSpace`` lives in
``show_text_line_and_space.py``.
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
from pypdfbox.contentstream.operator.text import (
    show_text_with_word_and_char_spacing as quote_module,
)
from pypdfbox.contentstream.operator.text.show_text_line_and_space import (
    ShowTextLineAndSpace,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString

ShowTextWithWordAndCharSpacing = quote_module.ShowTextWithWordAndCharSpacing


def test_operator_name_constant_is_quotation_mark() -> None:
    assert ShowTextWithWordAndCharSpacing.OPERATOR_NAME == '"'


def test_get_name_returns_quotation_mark() -> None:
    assert ShowTextWithWordAndCharSpacing().get_name() == '"'


def test_inherits_from_operator_processor() -> None:
    assert issubclass(ShowTextWithWordAndCharSpacing, OperatorProcessor)


def test_distinct_from_engine_coupled_show_text_line_and_space() -> None:
    assert ShowTextWithWordAndCharSpacing is not ShowTextLineAndSpace


def test_process_with_three_proper_operands_is_silent() -> None:
    """Happy path: ``"`` ships ``aw ac string`` — two numbers then a
    string. The lite stub logs and returns."""
    ShowTextWithWordAndCharSpacing().process(
        Operator.get_operator('"'),
        [COSFloat(2.0), COSFloat(0.5), COSString(b"hi")],
    )


def test_process_with_integer_spacings_is_silent() -> None:
    ShowTextWithWordAndCharSpacing().process(
        Operator.get_operator('"'),
        [COSInteger.get(3), COSInteger.get(1), COSString(b"x")],
    )


def test_process_with_zero_operands_does_not_raise() -> None:
    """Lite stub does not enforce arity — the rendering-cluster
    handler will raise once arity enforcement lands."""
    ShowTextWithWordAndCharSpacing().process(
        Operator.get_operator('"'), []
    )


def test_process_with_partial_operands_does_not_raise() -> None:
    """Two operands (missing the trailing string) — still silent."""
    ShowTextWithWordAndCharSpacing().process(
        Operator.get_operator('"'),
        [COSFloat(1.0), COSFloat(0.5)],
    )


def test_process_with_wrong_typed_operands_does_not_raise() -> None:
    ShowTextWithWordAndCharSpacing().process(
        Operator.get_operator('"'),
        [
            COSName.get_pdf_name("X"),
            COSName.get_pdf_name("Y"),
            COSInteger.get(1),
        ],
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    ShowTextWithWordAndCharSpacing().process(
        Operator.get_operator('"'),
        [COSFloat(1.0), COSFloat(0.2), COSString(b"x")],
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "ShowTextWithWordAndCharSpacing" in m and '"' in m
        for m in messages
    )


def test_processor_registered_for_quote_in_default_registry() -> None:
    handler = OperatorRegistry().lookup('"')
    assert isinstance(handler, ShowTextWithWordAndCharSpacing)


def test_registry_dispatch_does_not_raise() -> None:
    OperatorRegistry().process(
        Operator.get_operator('"'),
        [COSFloat(2.0), COSFloat(1.0), COSString(b"x")],
    )


def test_get_context_returns_none_for_standalone_use() -> None:
    assert ShowTextWithWordAndCharSpacing().get_context() is None

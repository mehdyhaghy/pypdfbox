"""Parity tests for the registry-stub ``SetTextMatrix`` (``Tm``).

Targets ``pypdfbox/contentstream/operator/text/set_text_matrix.py`` —
the lite registry-routing scaffold for ``Tm``. The engine-coupled
``SetMatrix`` handler (which actually pokes the text matrix on the
engine) lives in ``set_matrix.py`` and is tested separately.
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
from pypdfbox.contentstream.operator.text.set_matrix import SetMatrix
from pypdfbox.contentstream.operator.text.set_text_matrix import (
    SetTextMatrix,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName


def test_operator_name_constant_is_tm() -> None:
    assert SetTextMatrix.OPERATOR_NAME == "Tm"


def test_get_name_returns_tm() -> None:
    assert SetTextMatrix().get_name() == "Tm"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(SetTextMatrix, OperatorProcessor)


def test_distinct_from_engine_coupled_set_matrix() -> None:
    """Both classes mirror upstream's ``SetMatrix`` token (``Tm``) but
    the lite scaffold and the engine-coupled handler are intentionally
    distinct classes."""
    assert SetTextMatrix is not SetMatrix


def test_process_with_six_numeric_operands_is_silent() -> None:
    """``Tm`` ships exactly six numbers — the lite stub logs and
    returns."""
    SetTextMatrix().process(
        Operator.get_operator("Tm"),
        [
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(1.0),
            COSFloat(100.0),
            COSFloat(200.0),
        ],
    )


def test_process_with_integer_operands_is_silent() -> None:
    SetTextMatrix().process(
        Operator.get_operator("Tm"),
        [COSInteger.get(i) for i in (1, 0, 0, 1, 0, 0)],
    )


def test_process_with_too_few_operands_does_not_raise() -> None:
    """Lite stub is logging-only; arity enforcement lands with the
    rendering-cluster handler."""
    SetTextMatrix().process(
        Operator.get_operator("Tm"),
        [COSFloat(1.0), COSFloat(0.0)],
    )


def test_process_with_zero_operands_does_not_raise() -> None:
    SetTextMatrix().process(Operator.get_operator("Tm"), [])


def test_process_with_wrong_typed_operands_does_not_raise() -> None:
    SetTextMatrix().process(
        Operator.get_operator("Tm"),
        [COSName.get_pdf_name("X")] * 6,
    )


def test_process_logs_dispatch_at_debug_level(
    caplog: logging.LogRecord,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    SetTextMatrix().process(
        Operator.get_operator("Tm"),
        [COSFloat(v) for v in (1.0, 0.0, 0.0, 1.0, 10.0, 20.0)],
    )
    messages = [r.getMessage() for r in caplog.records]
    assert any("SetTextMatrix" in m and "Tm" in m for m in messages)


def test_processor_registered_for_tm_in_default_registry() -> None:
    handler = OperatorRegistry().lookup("Tm")
    assert isinstance(handler, SetTextMatrix)


def test_registry_dispatch_does_not_raise() -> None:
    OperatorRegistry().process(
        Operator.get_operator("Tm"),
        [COSFloat(1.0)] * 6,
    )


def test_get_context_returns_none_for_standalone_use() -> None:
    assert SetTextMatrix().get_context() is None

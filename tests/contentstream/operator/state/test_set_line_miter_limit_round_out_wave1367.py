"""Round-out tests for :class:`SetLineMiterLimit` (``M``) — wave 1367.

ISO 32000-1 §8.4.3.5: the miter-limit ``M`` operator takes a single
positive number that bounds the miter-spike ratio when ``j=0`` (miter
join). The class is a lite registry-routing stub — these tests pin down
the tolerance + dispatch shape.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.contentstream.operator.state.set_line_miter_limit import (
    SetLineMiterLimit,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


def test_class_attribute_matches_iso_token() -> None:
    """ISO 32000-1 §8.4.3.5 — uppercase ``M``."""
    assert SetLineMiterLimit.OPERATOR_NAME == "M"
    assert SetLineMiterLimit().get_name() == "M"


def test_subclass_relationship() -> None:
    assert issubclass(SetLineMiterLimit, OperatorProcessor)


@pytest.mark.parametrize(
    "limit",
    [1.0, 4.0, 10.0, 100.0],
    ids=["min_1", "default_4", "moderate_10", "extreme_100"],
)
def test_process_accepts_realistic_miter_limit_values(limit: float) -> None:
    """ISO 32000-1 §8.4.3.5: default is 10.0; values typically ≥1.0."""
    SetLineMiterLimit().process(
        Operator.get_operator("M"), [COSFloat(limit)]
    )


def test_process_accepts_integer_operand() -> None:
    SetLineMiterLimit().process(
        Operator.get_operator("M"), [COSInteger.get(4)]
    )


def test_process_accepts_zero_operand() -> None:
    """ISO recommends ≥1, but the stub tolerates anything numeric."""
    SetLineMiterLimit().process(
        Operator.get_operator("M"), [COSFloat(0.0)]
    )


def test_process_accepts_negative_operand() -> None:
    """Lite stub does no range enforcement."""
    SetLineMiterLimit().process(
        Operator.get_operator("M"), [COSFloat(-1.5)]
    )


def test_process_accepts_non_numeric_operand() -> None:
    """No type validation in the stub."""
    SetLineMiterLimit().process(
        Operator.get_operator("M"), [COSName.get_pdf_name("Bogus")]
    )
    SetLineMiterLimit().process(
        Operator.get_operator("M"), [COSString("bad")]
    )


def test_process_empty_operand_list_raises_missing_operand() -> None:
    """Upstream SetLineMiterLimit throws MissingOperandException on empty
    operands (oracle-pinned, wave 1534)."""
    with pytest.raises(MissingOperandException):
        SetLineMiterLimit().process(Operator.get_operator("M"), [])


def test_process_accepts_extra_operands_without_raising() -> None:
    SetLineMiterLimit().process(
        Operator.get_operator("M"),
        [COSFloat(4.0), COSFloat(5.0), COSFloat(6.0)],
    )


def test_process_emits_debug_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(
        logging.DEBUG, logger="pypdfbox.contentstream.operator.operator_processor"
    ):
        SetLineMiterLimit().process(
            Operator.get_operator("M"), [COSFloat(4.0)]
        )
    assert any(
        "SetLineMiterLimit dispatched" in r.message for r in caplog.records
    )


def test_default_registry_dispatches_capital_M() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("M")
    assert isinstance(handler, SetLineMiterLimit)
    registry.process(Operator.get_operator("M"), [COSFloat(4.0)])


def test_capital_M_is_not_lowercase_m_handler() -> None:
    """``M`` is miter-limit; lowercase ``m`` is the moveto path operator —
    they must dispatch to distinct classes."""
    registry = OperatorRegistry()
    miter = registry.lookup("M")
    moveto = registry.lookup("m")
    assert miter is not moveto
    assert type(miter).__name__ == "SetLineMiterLimit"
    # Don't pin the moveto class name — just confirm it's a different one.
    assert type(moveto).__name__ != "SetLineMiterLimit"


def test_get_context_is_none_for_standalone_use() -> None:
    assert SetLineMiterLimit().get_context() is None

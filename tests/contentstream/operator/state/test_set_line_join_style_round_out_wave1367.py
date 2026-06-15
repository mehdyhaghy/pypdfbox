"""Round-out tests for :class:`SetLineJoinStyle` (``j``) — wave 1367.

The class is a lite registry-routing stub. These tests pin down the
ISO 32000-1 §8.4.3.4 operand domain (0=miter, 1=round, 2=bevel) and the
malformed-stream tolerance contract.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.contentstream.operator.state.set_line_join_style import (
    SetLineJoinStyle,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


def test_class_attribute_matches_iso_token() -> None:
    """ISO 32000-1 §8.4.3.4 — the join-style operator is lowercase ``j``."""
    assert SetLineJoinStyle.OPERATOR_NAME == "j"
    assert SetLineJoinStyle().get_name() == "j"


def test_subclass_relationship() -> None:
    assert issubclass(SetLineJoinStyle, OperatorProcessor)


@pytest.mark.parametrize(
    "join",
    [0, 1, 2],
    ids=["miter_0", "round_1", "bevel_2"],
)
def test_process_accepts_every_iso_defined_join_value(join: int) -> None:
    """ISO 32000-1 §8.4.3.4 enumerates three join styles."""
    SetLineJoinStyle().process(
        Operator.get_operator("j"), [COSInteger.get(join)]
    )


def test_process_accepts_float_operand() -> None:
    """Stub tolerates a float operand without raising."""
    SetLineJoinStyle().process(Operator.get_operator("j"), [COSFloat(1.0)])


def test_process_accepts_out_of_range_integer() -> None:
    """Lite stub policy: values outside {0,1,2} accepted as-is."""
    SetLineJoinStyle().process(
        Operator.get_operator("j"), [COSInteger.get(-1)]
    )


def test_process_accepts_non_numeric_operand() -> None:
    """Stub does no validation."""
    SetLineJoinStyle().process(
        Operator.get_operator("j"), [COSName.get_pdf_name("Bad")]
    )
    SetLineJoinStyle().process(
        Operator.get_operator("j"), [COSString("Bad")]
    )


def test_process_empty_operand_list_raises_missing_operand() -> None:
    """Upstream SetLineJoinStyle throws MissingOperandException on empty
    operands (oracle-pinned, wave 1534)."""
    with pytest.raises(MissingOperandException):
        SetLineJoinStyle().process(Operator.get_operator("j"), [])


def test_process_accepts_extra_operands_without_raising() -> None:
    SetLineJoinStyle().process(
        Operator.get_operator("j"),
        [COSInteger.get(0), COSInteger.get(1), COSInteger.get(2)],
    )


def test_process_emits_debug_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(
        logging.DEBUG, logger="pypdfbox.contentstream.operator.operator_processor"
    ):
        SetLineJoinStyle().process(
            Operator.get_operator("j"), [COSInteger.get(1)]
        )
    assert any(
        "SetLineJoinStyle dispatched" in r.message for r in caplog.records
    )


def test_default_registry_dispatches_lowercase_j() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("j")
    assert isinstance(handler, SetLineJoinStyle)
    registry.process(Operator.get_operator("j"), [COSInteger.get(0)])


def test_lowercase_j_distinct_from_capital_J() -> None:
    """Case-sensitive lookup invariant."""
    registry = OperatorRegistry()
    cap = registry.lookup("J")
    join = registry.lookup("j")
    assert cap is not join
    assert type(join).__name__ == "SetLineJoinStyle"
    assert type(cap).__name__ == "SetLineCapStyle"


def test_get_context_is_none_for_standalone_use() -> None:
    assert SetLineJoinStyle().get_context() is None

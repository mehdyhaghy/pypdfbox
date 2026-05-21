"""Round-out tests for :class:`SetLineCapStyle` (``J``) — wave 1367.

The class is a lite registry-routing stub that ``_log_invocation``-s the
incoming operator. These tests pin down the stub's behaviour against the
full ISO 32000-1 §8.4.3.3 operand domain (0=butt, 1=round, 2=square) and
the malformed-stream tolerance contract.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import OperatorProcessor
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.contentstream.operator.state.set_line_cap_style import (
    SetLineCapStyle,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


def test_class_attribute_matches_iso_token() -> None:
    """ISO 32000-1 §8.4.3.3 — the cap-style operator is uppercase ``J``."""
    assert SetLineCapStyle.OPERATOR_NAME == "J"
    assert SetLineCapStyle().get_name() == "J"


def test_subclass_relationship() -> None:
    assert issubclass(SetLineCapStyle, OperatorProcessor)


@pytest.mark.parametrize(
    "cap",
    [0, 1, 2],
    ids=["butt_0", "round_1", "square_2"],
)
def test_process_accepts_every_iso_defined_cap_value(cap: int) -> None:
    """ISO 32000-1 §8.4.3.3 enumerates three cap styles."""
    SetLineCapStyle().process(
        Operator.get_operator("J"), [COSInteger.get(cap)]
    )


def test_process_accepts_float_operand_without_raising() -> None:
    """Streams in the wild sometimes serialise the cap value as a float."""
    SetLineCapStyle().process(Operator.get_operator("J"), [COSFloat(0.0)])


def test_process_accepts_out_of_range_integer() -> None:
    """Lite stub policy: values outside {0,1,2} are accepted as-is — range
    enforcement belongs to the rendering-prep cluster."""
    SetLineCapStyle().process(
        Operator.get_operator("J"), [COSInteger.get(99)]
    )


def test_process_accepts_non_numeric_operand() -> None:
    """Stub does no validation — even a malformed COSName/COSString
    operand must not raise."""
    SetLineCapStyle().process(
        Operator.get_operator("J"), [COSName.get_pdf_name("Bad")]
    )
    SetLineCapStyle().process(
        Operator.get_operator("J"), [COSString("Bad")]
    )


def test_process_accepts_empty_operand_list() -> None:
    """Short operand list is tolerated — no ``MissingOperandException``."""
    SetLineCapStyle().process(Operator.get_operator("J"), [])


def test_process_accepts_extra_operands_without_raising() -> None:
    """Trailing operands are silently ignored by the log stub."""
    SetLineCapStyle().process(
        Operator.get_operator("J"),
        [COSInteger.get(0), COSInteger.get(1), COSInteger.get(2)],
    )


def test_process_emits_debug_log(caplog: pytest.LogCaptureFixture) -> None:
    """The stub's only side effect: a debug-level log line per dispatch."""
    with caplog.at_level(
        logging.DEBUG, logger="pypdfbox.contentstream.operator.operator_processor"
    ):
        SetLineCapStyle().process(
            Operator.get_operator("J"), [COSInteger.get(1)]
        )
    assert any("SetLineCapStyle dispatched" in r.message for r in caplog.records)


def test_default_registry_dispatches_capital_J() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("J")
    assert isinstance(handler, SetLineCapStyle)
    # End-to-end dispatch via the registry must not raise.
    registry.process(Operator.get_operator("J"), [COSInteger.get(1)])


def test_capital_J_does_not_collide_with_lowercase_j() -> None:
    """``J`` (cap) and ``j`` (join) must dispatch to different classes —
    case-sensitive operator-name lookup is a parity-critical invariant."""
    registry = OperatorRegistry()
    cap_handler = registry.lookup("J")
    join_handler = registry.lookup("j")
    assert cap_handler is not join_handler
    assert type(cap_handler).__name__ == "SetLineCapStyle"
    assert type(join_handler).__name__ == "SetLineJoinStyle"


def test_get_context_is_none_for_standalone_use() -> None:
    """Registry-only path leaves the engine context unbound."""
    assert SetLineCapStyle().get_context() is None

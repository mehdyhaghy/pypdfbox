"""Round-out tests for :class:`SetFlatness` (``i``) — wave 1367.

ISO 32000-1 §10.6.2: the flatness ``i`` operator sets the flatness
tolerance in device pixels — number in the range 0..100, where 0 means
"device's default". The class is a lite registry-routing stub.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.contentstream.operator.state.set_flatness import SetFlatness
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


def test_class_attribute_matches_iso_token() -> None:
    """ISO 32000-1 §10.6.2 — lowercase ``i``."""
    assert SetFlatness.OPERATOR_NAME == "i"
    assert SetFlatness().get_name() == "i"


def test_subclass_relationship() -> None:
    assert issubclass(SetFlatness, OperatorProcessor)


@pytest.mark.parametrize(
    "flatness",
    [0.0, 0.5, 1.0, 10.0, 50.0, 100.0],
    ids=["device_default", "sub_unit", "one", "ten", "fifty", "max"],
)
def test_process_accepts_iso_in_range_values(flatness: float) -> None:
    """ISO 32000-1 §10.6.2 — flatness in 0..100."""
    SetFlatness().process(Operator.get_operator("i"), [COSFloat(flatness)])


def test_process_accepts_integer_operand() -> None:
    SetFlatness().process(Operator.get_operator("i"), [COSInteger.get(10)])


def test_process_accepts_out_of_range_value() -> None:
    """Stub does no range enforcement."""
    SetFlatness().process(Operator.get_operator("i"), [COSFloat(999.0)])
    SetFlatness().process(Operator.get_operator("i"), [COSFloat(-1.0)])


def test_process_accepts_non_numeric_operand() -> None:
    """No type validation in the stub."""
    SetFlatness().process(
        Operator.get_operator("i"), [COSName.get_pdf_name("Bogus")]
    )
    SetFlatness().process(
        Operator.get_operator("i"), [COSString("bad")]
    )


def test_process_empty_operand_list_raises_missing_operand() -> None:
    # Upstream SetFlatness throws MissingOperandException on empty operands
    # (oracle-pinned, wave 1534).
    with pytest.raises(MissingOperandException):
        SetFlatness().process(Operator.get_operator("i"), [])


def test_process_accepts_extra_operands_without_raising() -> None:
    SetFlatness().process(
        Operator.get_operator("i"), [COSFloat(1.0), COSFloat(2.0)]
    )


def test_process_emits_debug_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(
        logging.DEBUG, logger="pypdfbox.contentstream.operator.operator_processor"
    ):
        SetFlatness().process(Operator.get_operator("i"), [COSFloat(1.0)])
    assert any(
        "SetFlatness dispatched" in r.message for r in caplog.records
    )


def test_default_registry_dispatches_lowercase_i() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("i")
    assert isinstance(handler, SetFlatness)
    registry.process(Operator.get_operator("i"), [COSFloat(1.0)])


def test_get_context_is_none_for_standalone_use() -> None:
    assert SetFlatness().get_context() is None


def test_class_does_not_alias_other_state_operators() -> None:
    """Defensive: ``i`` (flatness) must be a distinct class from the
    other lite-stub state operators."""
    from pypdfbox.contentstream.operator.state.set_line_cap_style import (
        SetLineCapStyle,
    )
    from pypdfbox.contentstream.operator.state.set_line_join_style import (
        SetLineJoinStyle,
    )
    from pypdfbox.contentstream.operator.state.set_line_miter_limit import (
        SetLineMiterLimit,
    )

    assert SetFlatness is not SetLineCapStyle
    assert SetFlatness is not SetLineJoinStyle
    assert SetFlatness is not SetLineMiterLimit
    assert SetFlatness.OPERATOR_NAME not in {
        SetLineCapStyle.OPERATOR_NAME,
        SetLineJoinStyle.OPERATOR_NAME,
        SetLineMiterLimit.OPERATOR_NAME,
    }

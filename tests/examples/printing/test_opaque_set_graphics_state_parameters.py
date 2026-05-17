"""Tests for ``pypdfbox.examples.printing.opaque_set_graphics_state_parameters``."""
from __future__ import annotations

import logging

import pytest

from pypdfbox.contentstream.operator.operator_processor import OperatorProcessor
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.contentstream.operator_processor import MissingOperandException
from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.printing.opaque_set_graphics_state_parameters import (
    OpaqueSetGraphicsStateParameters,
)


def test_subclasses_operator_processor() -> None:
    assert issubclass(OpaqueSetGraphicsStateParameters, OperatorProcessor)


def test_get_name_returns_gs() -> None:
    op = OpaqueSetGraphicsStateParameters(None)
    assert op.get_name() == OperatorName.SET_GRAPHICS_STATE_PARAMS


def test_operator_name_classvar() -> None:
    assert (
        OpaqueSetGraphicsStateParameters.OPERATOR_NAME
        == OperatorName.SET_GRAPHICS_STATE_PARAMS
    )


class _FakeOperator:
    def get_name(self) -> str:
        return "gs"


def test_process_raises_on_empty_arguments() -> None:
    op = OpaqueSetGraphicsStateParameters(None)
    with pytest.raises(MissingOperandException):
        op.process(_FakeOperator(), [])


def test_process_returns_silently_for_non_name_operand() -> None:
    op = OpaqueSetGraphicsStateParameters(None)
    op.process(_FakeOperator(), [object()])


# ---------------------------------------------------------------------------
# Context-driven process() — exercises lines 40-53 (the meat of the op).
# ---------------------------------------------------------------------------


class _FakeExtGState:
    """Stand-in for :class:`PDExtendedGraphicsState` — records alpha clamps
    + lets us verify ``copy_into_graphics_state`` was called."""

    def __init__(self) -> None:
        self.non_stroking_alpha: float | None = None
        self.stroking_alpha: float | None = None
        self.copied_to: object | None = None

    def set_non_stroking_alpha_constant(self, value: float) -> None:
        self.non_stroking_alpha = value

    def set_stroking_alpha_constant(self, value: float) -> None:
        self.stroking_alpha = value

    def copy_into_graphics_state(self, gs: object) -> None:
        self.copied_to = gs


class _FakeResources:
    def __init__(self, mapping: dict[COSName, _FakeExtGState]) -> None:
        self._mapping = mapping

    def get_ext_g_state(self, name: COSName) -> _FakeExtGState | None:
        return self._mapping.get(name)


class _FakeContext:
    def __init__(self, resources: _FakeResources, gs: object) -> None:
        self._resources = resources
        self._gs = gs

    def get_resources(self) -> _FakeResources:
        return self._resources

    def get_graphics_state(self) -> object:
        return self._gs


def test_process_clamps_alpha_and_copies_state() -> None:
    """Happy path: a known /Foo ExtGState gets both alphas pinned to 1.0
    then copied into the engine's current graphics state."""
    name = COSName.get_pdf_name("Foo")
    ext = _FakeExtGState()
    gs = object()
    ctx = _FakeContext(_FakeResources({name: ext}), gs)
    op = OpaqueSetGraphicsStateParameters(ctx)

    op.process(_FakeOperator(), [name])

    assert ext.non_stroking_alpha == 1.0
    assert ext.stroking_alpha == 1.0
    # Engine graphics state was the merge target.
    assert ext.copied_to is gs


def test_process_returns_silently_when_context_is_none() -> None:
    """Standalone registry use leaves ``_context`` as ``None`` -> early
    return after the name check (covers line 43)."""
    name = COSName.get_pdf_name("AnyName")
    op = OpaqueSetGraphicsStateParameters(None)
    # Should not raise — early-return branch.
    op.process(_FakeOperator(), [name])


def test_process_logs_and_returns_when_name_missing_from_resources(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown name -> ``_log.error`` + early return (lines 46-50)."""
    missing = COSName.get_pdf_name("Missing")
    # Empty resources mapping forces ``get_ext_g_state`` to return None.
    ctx = _FakeContext(_FakeResources({}), object())
    op = OpaqueSetGraphicsStateParameters(ctx)

    with caplog.at_level(
        logging.ERROR,
        logger=(
            "pypdfbox.examples.printing.opaque_set_graphics_state_parameters"
        ),
    ):
        op.process(_FakeOperator(), [missing])
    # Error message must mention the name token.
    assert any("Missing" in rec.message for rec in caplog.records)


def test_process_ignores_extra_operands_after_first(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Upstream only inspects operands[0]; trailing operands are ignored."""
    name = COSName.get_pdf_name("Foo")
    ext = _FakeExtGState()
    ctx = _FakeContext(_FakeResources({name: ext}), object())
    op = OpaqueSetGraphicsStateParameters(ctx)
    op.process(_FakeOperator(), [name, object(), object()])
    assert ext.non_stroking_alpha == 1.0
    assert ext.stroking_alpha == 1.0

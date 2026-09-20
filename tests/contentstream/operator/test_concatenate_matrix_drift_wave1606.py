"""PDFBOX-6255 — the generic-engine ``cm`` handler cannot drift.

``graphics.ConcatenateMatrix`` is the handler actually registered for
``cm`` by ``PDFGraphicsStreamEngine`` / ``OperatorRegistry``. It routes
through ``PDFStreamEngine.transform``, whose base implementation is a
no-op, so nothing raises there today — which is exactly why wave 1605's
fix to ``state.Concatenate`` did not reach it. It now carries the same
``ValueError`` -> ``OSError`` translation, so a subclass whose
``transform`` concatenates through :class:`Matrix` reports the failure as
upstream's ``IOException`` rather than leaking an unchecked exception out
of the operator dispatch loop.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.graphics.concatenate_matrix import ConcatenateMatrix
from pypdfbox.contentstream.operator.state.concatenate import check_concatenation
from pypdfbox.cos import COSFloat

_HUGE = 3.4e38


class _Context:
    """Engine stand-in whose ``transform`` hook actually concatenates, so
    it can fail the way a rendering subclass would."""

    def __init__(self, ctm: tuple[float, ...]) -> None:
        self.ctm = ctm

    def transform(self, matrix: tuple[float, ...]) -> None:
        check_concatenation(matrix, self.ctm)
        self.ctm = matrix


def _operands(*values: float) -> list[Any]:
    return [COSFloat(v) for v in values]


def _process(ctx: _Context, *values: float) -> None:
    processor = ConcatenateMatrix()
    processor.set_context(ctx)  # type: ignore[arg-type]
    processor.process(Operator.get_operator("cm"), _operands(*values))


def test_transform_value_error_is_rethrown_as_oserror() -> None:
    ctx = _Context((_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0))
    with pytest.raises(OSError, match="Multiplying two matrices produces illegal"):
        _process(ctx, _HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)


def test_rethrown_error_chains_the_original() -> None:
    ctx = _Context((_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0))
    with pytest.raises(OSError) as exc:
        _process(ctx, _HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
    assert not isinstance(exc.value, ValueError)
    assert isinstance(exc.value.__cause__, ValueError)


def test_no_op_transform_hook_still_does_nothing() -> None:
    """The base engine's ``transform`` is a no-op; the new try/except must
    not turn that into an error."""

    class _NoOpContext:
        def transform(self, matrix: tuple[float, ...]) -> None:
            self.seen = matrix

    ctx = _NoOpContext()
    processor = ConcatenateMatrix()
    processor.set_context(ctx)  # type: ignore[arg-type]
    processor.process(Operator.get_operator("cm"), _operands(2.0, 0.0, 0.0, 3.0, 4.0, 5.0))
    assert ctx.seen == pytest.approx((2.0, 0.0, 0.0, 3.0, 4.0, 5.0))


def test_singular_matrix_is_not_rejected() -> None:
    ctx = _Context((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    _process(ctx, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert ctx.ctm == pytest.approx((0.0, 0.0, 0.0, 0.0, 0.0, 0.0))

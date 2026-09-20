"""PDFBOX-6255 — ``cm`` rethrows a matrix failure as an I/O error.

``Matrix.concatenate`` refuses a product containing NaN / infinity
(``checkFloatValues`` -> ``IllegalArgumentException`` upstream, ported as
``ValueError``). That unchecked exception used to escape the operator
dispatch loop and abort the whole page walk with a non-``IOException``;
upstream 3.0.9 wraps the call and rethrows as ``IOException``
(``OSError`` here) so the engine's normal malformed-operator handling
applies.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.state.concatenate import Concatenate
from pypdfbox.cos import COSFloat, COSName
from pypdfbox.util.matrix import Matrix

# float32 max — squaring it overflows to +inf.
_HUGE = 3.4e38


class _GraphicsState:
    def __init__(self, ctm: Matrix) -> None:
        self._ctm = ctm

    def get_current_transformation_matrix(self) -> Matrix:
        return self._ctm


class _Context:
    """Engine stand-in without a ``transform`` hook, so ``Concatenate``
    takes the ``getCurrentTransformationMatrix().concatenate(...)`` path
    that upstream wraps."""

    def __init__(self, ctm: Matrix) -> None:
        self._gs = _GraphicsState(ctm)

    def get_graphics_state(self) -> _GraphicsState:
        return self._gs


def _operands(*values: float) -> list[Any]:
    return [COSFloat(v) for v in values]


def _process(ctm: Matrix, *values: float) -> _Context:
    processor = Concatenate()
    processor.set_context(_Context(ctm))  # type: ignore[arg-type]
    processor.process(Operator.get_operator("cm"), _operands(*values))
    return processor.get_context()  # type: ignore[return-value]


def test_overflowing_matrix_raises_oserror() -> None:
    ctm = Matrix(_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
    with pytest.raises(OSError, match="Multiplying two matrices produces illegal"):
        _process(ctm, _HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)


def test_value_error_is_not_leaked_untranslated() -> None:
    """The raised object must be an ``OSError`` (upstream ``IOException``)
    and must chain the original matrix failure."""
    ctm = Matrix(_HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
    with pytest.raises(OSError) as exc:
        _process(ctm, _HUGE, 0.0, 0.0, _HUGE, 0.0, 0.0)
    assert not isinstance(exc.value, ValueError)
    assert isinstance(exc.value.__cause__, ValueError)


def test_well_formed_matrix_still_concatenates() -> None:
    ctm = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    ctx = _process(ctm, 2.0, 0.0, 0.0, 3.0, 10.0, 20.0)
    result = ctx.get_graphics_state().get_current_transformation_matrix()
    assert result.get_scale_x() == pytest.approx(2.0)
    assert result.get_scale_y() == pytest.approx(3.0)
    assert result.get_translate_x() == pytest.approx(10.0)
    assert result.get_translate_y() == pytest.approx(20.0)


def test_singular_matrix_is_not_rejected() -> None:
    """Upstream only rejects non-finite products; a degenerate (all-zero,
    non-invertible) matrix is legal PDF and must still be applied."""
    ctm = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    ctx = _process(ctm, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    result = ctx.get_graphics_state().get_current_transformation_matrix()
    assert result.get_scale_x() == pytest.approx(0.0)
    assert result.get_scale_y() == pytest.approx(0.0)


def test_non_numeric_operand_is_still_a_silent_skip() -> None:
    """The try/except must not change the ``checkArrayTypesClass`` skip."""
    ctm = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    processor = Concatenate()
    processor.set_context(_Context(ctm))  # type: ignore[arg-type]
    operands: list[Any] = [*_operands(1.0, 0.0, 0.0, 1.0, 5.0), COSName.get_pdf_name("X")]
    processor.process(Operator.get_operator("cm"), operands)
    assert ctm.get_translate_x() == pytest.approx(0.0)

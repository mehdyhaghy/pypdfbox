from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class SetDashPattern(OperatorProcessor):
    """``d`` — Set the line dash pattern. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineDashPattern``.

    Operand validation matches upstream:

    * Fewer than two operands raises :class:`MissingOperandException`.
    * If the first operand is not a :class:`COSArray`, the operator is
      silently skipped (upstream ``return``s after the ``instanceof``
      check).
    * If the second operand is not a :class:`COSNumber`, the operator
      is silently skipped likewise.

    Upstream additionally inspects the dash array for non-number
    elements and warn-logs / replaces it with an empty (solid) array;
    that sanitisation step lands with the rendering-prep cluster, since
    the lite registry-routing scaffold has no graphics state yet to
    forward the cleaned array into.
    """

    OPERATOR_NAME = "d"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSArray):
            return
        if not isinstance(operands[1], COSNumber):
            return
        self._log_invocation(operator, operands)

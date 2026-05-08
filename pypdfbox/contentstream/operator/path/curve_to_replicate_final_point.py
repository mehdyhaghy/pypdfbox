from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class CurveToReplicateFinalPoint(OperatorProcessor):
    """``y`` — Append a cubic Bezier curve to the current path using
    the new endpoint as the second control point. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.CurveToReplicateFinalPoint``.

    Operand validation matches upstream:

    * Fewer than four operands raises :class:`MissingOperandException`.
    * If any of the first four operands is not a :class:`COSNumber`, the
      operator is silently skipped (upstream calls
      ``checkArrayTypesClass`` on the consumed operand window). Trailing
      operands are ignored.

    The path-construction bookkeeping arrives with the rendering cluster;
    until then a successful validation reduces to the existing debug-log
    no-op.
    """

    OPERATOR_NAME = "y"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 4:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands[:4], COSNumber):
            return
        self._log_invocation(operator, operands)

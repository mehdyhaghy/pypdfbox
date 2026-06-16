from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class CurveToReplicateInitialPoint(OperatorProcessor):
    """``v`` — Append a cubic Bezier curve to the current path using
    the current point as the first control point. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.CurveToReplicateInitialPoint``.

    Operand validation matches upstream:

    * Fewer than four operands raises :class:`MissingOperandException`.
    * If any operand is not a :class:`COSNumber`, the operator is
      silently skipped (upstream calls ``checkArrayTypesClass`` over the
      WHOLE operand list, so a trailing non-number is a silent no-op too,
      not accepted-with-trailing-ignored).

    The path-construction bookkeeping arrives with the rendering cluster;
    until then a successful validation reduces to the existing debug-log
    no-op.
    """

    OPERATOR_NAME = "v"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 4:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands, COSNumber):
            return
        self._log_invocation(operator, operands)

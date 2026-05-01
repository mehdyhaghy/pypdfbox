from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class MoveTo(OperatorProcessor):
    """``m`` — Begin a new subpath at ``(x, y)``. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.MoveTo``.

    Operand validation matches upstream:

    * Fewer than two operands raises :class:`MissingOperandException`
      (upstream throws the same exception type).
    * If either of the first two operands is not a :class:`COSNumber`,
      the operator is silently skipped — upstream returns without
      raising, mirroring PDFBox's leniency for malformed streams.

    The path-construction bookkeeping (``moveTo`` on the graphics
    context) lands with the rendering cluster; until then a successful
    validation reduces to the existing debug-log no-op.
    """

    OPERATOR_NAME = "m"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSNumber):
            return
        if not isinstance(operands[1], COSNumber):
            return
        self._log_invocation(operator, operands)

from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class AppendRectangle(OperatorProcessor):
    """``re`` — Append a rectangle to the current path as a complete
    subpath. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.AppendRectangleToPath``.

    Operand validation matches upstream:

    * Fewer than four operands raises :class:`MissingOperandException`.
    * If any of the first four operands is not a :class:`COSNumber`,
      the operator is silently skipped (upstream calls
      ``checkArrayTypesClass`` on the consumed operand window and returns
      when it reports a mismatch). Trailing operands are ignored.

    The actual rectangle-construction call (``appendRectangle`` on the
    graphics context) arrives with the rendering cluster; for now a
    successful validation reduces to the existing debug-log no-op.
    """

    OPERATOR_NAME = "re"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 4:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands[:4], COSNumber):
            return
        self._log_invocation(operator, operands)

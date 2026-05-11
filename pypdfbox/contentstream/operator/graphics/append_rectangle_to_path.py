from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class AppendRectangleToPath(GraphicsOperatorProcessor):
    """``re`` — Append a rectangle to the current path as a complete
    subpath. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.AppendRectangleToPath``
    (upstream lines 36–81).

    Operand validation matches upstream:

    * Fewer than four operands raises :class:`MissingOperandException`.
    * If any of the first four operands is not a :class:`COSNumber`,
      the operator is silently skipped (upstream calls
      ``checkArrayTypesClass`` and returns when it reports a mismatch).
    """

    OPERATOR_NAME = OperatorName.APPEND_RECT

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 4:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands[:4], COSNumber):
            return
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.APPEND_RECT


__all__ = ["AppendRectangleToPath"]

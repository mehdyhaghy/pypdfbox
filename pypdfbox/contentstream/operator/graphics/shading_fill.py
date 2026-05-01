from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class ShadingFill(OperatorProcessor):
    """``sh`` — Paint the shape and colour shading described by the
    shading dictionary referenced by the named resource (``/Shading``
    sub-resource on the current page or form XObject). Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.ShadingFill``.

    Operand validation matches upstream:

    * Fewer than one operand raises :class:`MissingOperandException`
      (upstream throws the same exception type).
    * If the first operand is not a :class:`COSName`, the operator is
      silently skipped — upstream raises ``MissingOperandException``,
      but pypdfbox follows the leniency precedent of the path
      operators (``MoveTo``, ``LineTo``, ``CurveTo``,
      ``AppendRectangleToPath``) and returns without raising for type
      mismatches in malformed streams.

    The shading-resource lookup and dispatch to the shading-type
    painter lands with the rendering cluster; until then a successful
    validation reduces to the existing debug-log no-op.
    """

    OPERATOR_NAME = "sh"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 1:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSName):
            return
        self._log_invocation(operator, operands)

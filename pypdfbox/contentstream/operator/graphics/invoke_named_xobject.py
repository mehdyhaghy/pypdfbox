from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class InvokeNamedXObject(OperatorProcessor):
    """``Do`` — Paint the form or image XObject referenced by the named
    resource. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.DrawObject``.

    Operand validation matches upstream:

    * Fewer than one operand raises :class:`MissingOperandException`
      (upstream throws the same exception type).
    * If the first operand is not a :class:`COSName`, the operator is
      silently skipped — mirrors upstream's early-return on the
      ``instanceof COSName`` guard.

    XObject resolution and painting land with the rendering cluster;
    until then a successful validation reduces to the existing
    debug-log no-op.
    """

    OPERATOR_NAME = "Do"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 1:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSName):
            return
        self._log_invocation(operator, operands)

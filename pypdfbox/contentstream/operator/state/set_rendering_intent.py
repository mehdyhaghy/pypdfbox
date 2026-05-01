from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class SetRenderingIntent(OperatorProcessor):
    """``ri`` — Set the colour rendering intent in the graphics state.
    Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetRenderingIntent``.

    Operand validation matches upstream:

    * Empty operand list raises :class:`MissingOperandException`.
    * If the first operand is not a :class:`COSName`, the operator is
      silently skipped (upstream ``return``s after the ``instanceof``
      check).

    Upstream additionally resolves the name through ``RenderingIntent
    .fromString`` and stores it on the current graphics state; that
    bookkeeping step lands with the rendering-prep cluster, since the
    lite registry-routing scaffold has no graphics-state object yet.
    """

    OPERATOR_NAME = "ri"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSName):
            return
        self._log_invocation(operator, operands)

from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class LineTo(OperatorProcessor):
    """``l`` — Append a straight-line segment to the current subpath.
    Mirrors ``org.apache.pdfbox.contentstream.operator.graphics.LineTo``.

    Operand validation matches upstream:

    * Fewer than two operands raises :class:`MissingOperandException`.
    * If either of the first two operands is not a :class:`COSNumber`,
      the operator is silently skipped (upstream ``return``s after the
      ``instanceof`` check).

    Upstream additionally warn-logs and falls back to ``moveTo`` when
    invoked without a prior ``MoveTo`` (no current point); that
    behavioural fallback lands with the rendering cluster, since the
    lite registry-routing scaffold has no current-point state yet.
    """

    OPERATOR_NAME = "l"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSNumber):
            return
        if not isinstance(operands[1], COSNumber):
            return
        self._log_invocation(operator, operands)

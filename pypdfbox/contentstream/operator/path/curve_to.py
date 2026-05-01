from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class CurveTo(OperatorProcessor):
    """``c`` — Append a cubic Bezier curve to the current path using
    two explicit control points. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.CurveTo``.

    Operand validation matches upstream:

    * Fewer than six operands raises :class:`MissingOperandException`.
    * If any operand is not a :class:`COSNumber`, the operator is
      silently skipped (upstream calls ``checkArrayTypesClass``).

    Upstream additionally warn-logs and falls back to ``moveTo(x3, y3)``
    when invoked without a prior ``MoveTo``; that behavioural fallback
    lands with the rendering cluster, since the lite registry-routing
    scaffold has no current-point state yet.
    """

    OPERATOR_NAME = "c"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 6:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands, COSNumber):
            return
        self._log_invocation(operator, operands)

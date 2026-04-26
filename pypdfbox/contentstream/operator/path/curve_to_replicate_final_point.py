from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class CurveToReplicateFinalPoint(OperatorProcessor):
    """``y`` — Append a cubic Bezier curve to the current path using
    the new endpoint as the second control point. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.CurveToReplicateFinalPoint``.

    Lite stub: registry-routing scaffold only — the path-construction
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "y"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

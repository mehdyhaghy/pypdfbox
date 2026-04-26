from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class CurveToReplicateInitialPoint(OperatorProcessor):
    """``v`` — Append a cubic Bezier curve to the current path using
    the current point as the first control point. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.CurveToReplicateInitialPoint``.

    Lite stub: registry-routing scaffold only — the path-construction
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "v"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class CurveTo(OperatorProcessor):
    """``c`` — Append a cubic Bezier curve to the current path using
    two explicit control points. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.CurveTo``.

    Lite stub: registry-routing scaffold only — the path-construction
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "c"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

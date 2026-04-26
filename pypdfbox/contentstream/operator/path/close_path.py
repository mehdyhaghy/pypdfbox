from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class ClosePath(OperatorProcessor):
    """``h`` — Close the current subpath by appending a straight-line
    segment from the current point to the subpath's starting point.
    Mirrors ``org.apache.pdfbox.contentstream.operator.graphics.ClosePath``.

    Lite stub: registry-routing scaffold only — the path-construction
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "h"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

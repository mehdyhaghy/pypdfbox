from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetDashPattern(OperatorProcessor):
    """``d`` — Set the line dash pattern. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineDashPattern``.

    Lite stub: registry-routing scaffold only — dash-pattern bookkeeping
    lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "d"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

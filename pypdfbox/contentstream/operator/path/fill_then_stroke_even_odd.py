from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class FillThenStrokeEvenOdd(OperatorProcessor):
    """``B*`` — Fill and then stroke the current path using the even-odd
    rule. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.FillAndStrokeEvenOddRule``.

    Lite stub: registry-routing scaffold only — the path-painting
    pipeline arrives with the rendering cluster.
    """

    OPERATOR_NAME = "B*"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

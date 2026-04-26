from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class FillPathNonZeroWinding(OperatorProcessor):
    """``f`` — Fill the current path using the non-zero winding number
    rule. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.FillNonZeroRule``.

    Lite stub: registry-routing scaffold only — the path-painting
    pipeline arrives with the rendering cluster.
    """

    OPERATOR_NAME = "f"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

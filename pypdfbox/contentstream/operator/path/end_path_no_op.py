from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class EndPathNoOp(OperatorProcessor):
    """``n`` — End the path object without filling or stroking it. Used
    primarily to set a clipping region. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.EndPath``.

    Lite stub: registry-routing scaffold only — the path-painting
    pipeline arrives with the rendering cluster.
    """

    OPERATOR_NAME = "n"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

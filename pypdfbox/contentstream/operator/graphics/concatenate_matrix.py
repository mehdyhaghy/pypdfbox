from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class ConcatenateMatrix(OperatorProcessor):
    """``cm`` — Concatenate a matrix to the current transformation
    matrix. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.Concatenate``.

    Lite stub: registry-routing scaffold only — graphics-state matrix
    bookkeeping lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "cm"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

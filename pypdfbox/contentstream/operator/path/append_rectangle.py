from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class AppendRectangle(OperatorProcessor):
    """``re`` — Append a rectangle to the current path as a complete
    subpath. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.AppendRectangleToPath``.

    Lite stub: registry-routing scaffold only — the path-construction
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "re"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

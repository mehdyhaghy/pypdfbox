from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class MoveTo(OperatorProcessor):
    """``m`` — Begin a new subpath at ``(x, y)``. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.MoveTo``.

    Lite stub: registry-routing scaffold only — the path-construction
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "m"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

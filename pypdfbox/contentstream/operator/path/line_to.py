from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class LineTo(OperatorProcessor):
    """``l`` — Append a straight-line segment to the current subpath.
    Mirrors ``org.apache.pdfbox.contentstream.operator.graphics.LineTo``.

    Lite stub: registry-routing scaffold only — the path-construction
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "l"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

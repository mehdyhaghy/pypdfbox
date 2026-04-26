from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class CloseAndStrokePath(OperatorProcessor):
    """``s`` — Close and stroke the current path. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.CloseAndStrokePath``.

    Lite stub: registry-routing scaffold only — the path-painting
    pipeline arrives with the rendering cluster.
    """

    OPERATOR_NAME = "s"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

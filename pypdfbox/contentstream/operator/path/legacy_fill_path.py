from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class LegacyFillPath(OperatorProcessor):
    """``F`` — Equivalent to ``f``. Included for backwards compatibility
    with PDF 1.0 producers. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.LegacyFillNonZeroRule``.

    Lite stub: registry-routing scaffold only — the path-painting
    pipeline arrives with the rendering cluster.
    """

    OPERATOR_NAME = "F"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class ClipNonZeroWinding(OperatorProcessor):
    """``W`` — Modify the current clipping path by intersecting it with
    the current path using the non-zero winding number rule. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.ClipNonZeroRule``.

    Lite stub: registry-routing scaffold only — the clipping pipeline
    arrives with the rendering cluster.
    """

    OPERATOR_NAME = "W"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

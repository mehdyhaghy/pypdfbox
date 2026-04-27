from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetLineWidth(OperatorProcessor):
    """``w`` — Set the line width in the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineWidth``.

    Lite stub: registry-routing scaffold only — graphics-state
    line-width bookkeeping lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "w"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

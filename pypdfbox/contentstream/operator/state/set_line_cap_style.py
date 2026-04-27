from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetLineCapStyle(OperatorProcessor):
    """``J`` — Set the line cap style in the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineCapStyle``.

    Lite stub: registry-routing scaffold only — graphics-state
    line-cap bookkeeping lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "J"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
